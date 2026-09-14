"""
Picks up document_mart rows with no chunks yet, fetches the right source
text (translated_text if the document wasn't originally English, otherwise
the original staging extracted_text), chunks it, embeds each chunk, writes
to vector_mart_chunks (Postgres, for BM25) AND Chroma (for vector search).

Usage:
    python MAIN.py
"""
import uuid

from DB import get_connection
from CHUNKER import chunk_text
from EMBEDDER import embed_text
from CHROMA_CLIENT import upsert_chunk


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

            upsert_chunk(
                chunk_id=chunk_id,
                embedding=embedding,
                document=piece,
                metadata={
                    "document_mart_id": doc_id_str,
                    "department": department or "",
                    "doc_type": doc_type or "",
                    "language": language or "",
                    "chunk_index": idx,
                },
            )

            cur.execute(
                """
                INSERT INTO vector_mart_chunks
                    (id, document_mart_id, chunk_index, content, embedding_ref, embedding_model)
                VALUES (%s, %s, %s, %s, %s, 'nomic-embed-text')
                """,
                (chunk_id, doc_id_str, idx, piece, chunk_id),
            )

        conn.commit()
        print(f"[{doc_id_str}] indexed.")

    cur.close()
    conn.close()
    print("Done. Next: RAG_SERVICE query endpoint.")


if __name__ == "__main__":
    run()