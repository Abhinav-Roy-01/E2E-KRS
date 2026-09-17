"""
Picks up document_mart rows with no chunks yet, fetches the right source
text (translated_text if the document wasn't originally English, otherwise
the original staging extracted_text), chunks it, embeds each chunk, writes
to vector_mart_chunks (Postgres, for BM25/sparse) AND context_document
(Postgres+pgvector, for dense vector search -- see VECTOR_STORE.py for why
this replaced Chroma: same table shape and embedding model AICTE's context
store uses, so both arms' vectors are directly comparable).

Usage:
    python MAIN.py
"""
import os
import uuid

from DB import get_connection
from CHUNKER import chunk_text
from EMBEDDER import embed_text, MODEL as EMBEDDING_MODEL
import VECTOR_STORE


def get_source_text(cur, document_mart_id):
    cur.execute(
        """
        SELECT i.translated_text, s.extracted_text
        FROM document_mart d
        JOIN intermediate_documents i ON i.id = d.intermediate_document_id
        JOIN staging_documents s ON s.id = i.staging_document_id
        WHERE d.id = %s
        """,
        (document_mart_id,),
    )
    row = cur.fetchone()
    if not row:
        return ""
    translated_text, extracted_text = row
    return translated_text if translated_text else extracted_text


def run():
    conn = get_connection()
    try:
        from pgvector.psycopg import register_vector
        register_vector(conn)
    except ImportError:
        raise RuntimeError("pgvector not installed -- pip install -r REQUIREMENTS.TXT")
    cur = conn.cursor()

    cur.execute(
        """
        SELECT d.id, d.department, d.doc_type, d.language
        FROM document_mart d
        LEFT JOIN vector_mart_chunks v ON v.document_mart_id = d.id
        WHERE d.mart_status = 'active' AND v.id IS NULL
        """
    )
    pending = cur.fetchall()
    print(f"Found {len(pending)} document(s) pending embedding.")

    for doc_id, department, doc_type, language in pending:
        doc_id_str = str(doc_id)
        text = get_source_text(cur, doc_id_str)
        if not text:
            print(f"[{doc_id_str}] no source text found, skipping.")
            continue

        pieces = chunk_text(text)
        print(f"[{doc_id_str}] split into {len(pieces)} chunk(s).")

        for idx, piece in enumerate(pieces):
            embedding = embed_text(piece)
            chunk_id = str(uuid.uuid4())

            VECTOR_STORE.insert_context(
                conn,
                entity_id=doc_id_str,
                entity_type="document",
                context_type=doc_type or None,
                context_text=piece,
                embedding=embedding,
                source_database="ekrs",
                source_table="document_mart",
                source_record_id=doc_id_str,
            )

            cur.execute(
                """
                INSERT INTO vector_mart_chunks
                    (id, document_mart_id, chunk_index, content, embedding_ref, embedding_model)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (chunk_id, doc_id_str, idx, piece, chunk_id, EMBEDDING_MODEL),
            )

        conn.commit()
        print(f"[{doc_id_str}] indexed.")

    cur.close()
    conn.close()
    print("Done. Next: RAG_SERVICE query endpoint.")


if __name__ == "__main__":
    run()