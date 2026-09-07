"""
Picks up intermediate_documents where intermediate_status='classified',
promotes to a governed document_mart record IF classification confidence
is high enough (>=0.85, matching the earlier design's confidence gate) --
otherwise flags for human review instead of silently promoting a possibly-
wrong classification.

storage_path is computed deterministically (ROUTING.py) -- never by asking
the LLM to produce a filesystem path directly.

NOTE (known gap, not solved here): the 'deadline' field the classifier
extracts isn't persisted anywhere upstream (intermediate_documents has no
deadline column), so compliance_flags can't be populated yet even though
document_mart now exists. This is a real gap, flagged rather than silently
dropped -- fixing it means adding a deadline column to intermediate_documents
and threading it through WAREHOUSE/INTERMEDIATE, not solved in this file.

Usage:
    python MAIN.py
"""
from DB import get_connection
from ROUTING import build_storage_path

CONFIDENCE_THRESHOLD = 0.85


def run():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            i.id, i.department, i.doc_type, i.classification_confidence,
            s.language, s.raw_document_id,
            r.original_filename, r.storage_key
        FROM intermediate_documents i
        JOIN staging_documents s ON s.id = i.staging_document_id
        JOIN raw_documents r ON r.id = s.raw_document_id
        WHERE i.intermediate_status = 'classified'
        """
    )
    pending = cur.fetchall()
    print(f"Found {len(pending)} document(s) pending promotion.")

    for (intermediate_id, department, doc_type, confidence,
         language, raw_doc_id, filename, storage_key) in pending:
        intermediate_id_str = str(intermediate_id)

        if not department or not doc_type or confidence is None or confidence < CONFIDENCE_THRESHOLD:
            print(f"[{intermediate_id_str}] confidence {confidence} below threshold "
                  f"({CONFIDENCE_THRESHOLD}) or missing fields -- flagging for review.")
            cur.execute(
                "UPDATE intermediate_documents SET intermediate_status = 'needs_review' WHERE id = %s",
                (intermediate_id_str,),
            )
            conn.commit()
            continue

        storage_path = build_storage_path(department, doc_type, filename)
        print(f"[{intermediate_id_str}] promoting -> {storage_path}")

        cur.execute(
            """
            INSERT INTO document_mart
                (intermediate_document_id, original_filename, department, doc_type,
                 language, storage_path, storage_key, sensitivity_tier, mart_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'internal', 'active')
            RETURNING id
            """,
            (intermediate_id_str, filename, department, doc_type, language, storage_path, storage_key),
        )
        document_mart_id = cur.fetchone()[0]

        cur.execute(
            "UPDATE intermediate_documents SET intermediate_status = 'promoted' WHERE id = %s",
            (intermediate_id_str,),
        )
        conn.commit()
        print(f"[{intermediate_id_str}] promoted as document_mart.id={document_mart_id}")

    cur.close()
    conn.close()
    print("Done. Next: chunking + embedding (WAREHOUSE/MARTS/VECTOR_MART).")


if __name__ == "__main__":
    run()