"""
Picks up staging_documents where staging_status='staged', classifies
(department/doc_type/deadline/confidence) on the ORIGINAL-LANGUAGE text,
translates to English if not already English, writes an
intermediate_documents row, advances staging_status to 'classified'.

Similarity-based dedup (intermediate_documents.similarity_verdict) is NOT
done here yet -- deferred to a follow-up, per the build-order decision to
prove classification + translation first before adding dedup logic.

Usage:
    python MAIN.py
"""
from DB import get_connection
from CLASSIFIER import classify_document
from TRANSLATOR import translate


def run():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT s.id, s.raw_document_id, s.extracted_text, s.language
        FROM staging_documents s
        WHERE s.staging_status = 'staged'
        """
    )
    pending = cur.fetchall()
    print(f"Found {len(pending)} document(s) pending classification/translation.")

    for staging_id, raw_doc_id, text, language in pending:
        staging_id_str = str(staging_id)
        print(f"[{staging_id_str}] classifying (language={language}) ...")

        classification = classify_document(text)
        print(f"[{staging_id_str}] classified as: {classification}")
        # NOTE: classification['deadline'] is captured here but NOT persisted
        # yet -- compliance_flags is keyed to document_mart_id, which doesn't
        # exist until promotion (WAREHOUSE/MARTS/DOCUMENT_MART). Carry this
        # value forward when that stage is built, don't drop it silently.

        translated_text = None
        translation_confidence = None
        if language and language != "en":
            print(f"[{staging_id_str}] translating from '{language}' to 'en' ...")
            try:
                result = translate(text, source_lang=language, target_lang="en")
                translated_text = result["translated_text"]
                translation_confidence = result["confidence_score"]
                if translation_confidence < 1.0:
                    print(f"[{staging_id_str}] LOW CONFIDENCE translation -- flag for review.")
            except ValueError as e:
                print(f"[{staging_id_str}] translation skipped: {e}")
        else:
            print(f"[{staging_id_str}] already English, skipping translation.")

        cur.execute(
            """
            INSERT INTO intermediate_documents
                (staging_document_id, department, doc_type, classification_confidence,
                 translated_text, translation_confidence, intermediate_status)
            VALUES (%s, %s, %s, %s, %s, %s, 'classified')
            """,
            (
                staging_id_str,
                classification.get("department"),
                classification.get("doc_type"),
                classification.get("confidence"),
                translated_text,
                translation_confidence,
            ),
        )
        cur.execute(
            "UPDATE staging_documents SET staging_status = 'classified' WHERE id = %s",
            (staging_id_str,),
        )
        conn.commit()
        print(f"[{staging_id_str}] done.")

    cur.close()
    conn.close()
    print("Done. Next: similarity-dedup, then promotion to document_mart.")


if __name__ == "__main__":
    run()
