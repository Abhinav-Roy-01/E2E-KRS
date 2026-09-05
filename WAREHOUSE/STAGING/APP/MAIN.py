"""
Picks up raw_documents where raw_status='received', downloads from MinIO,
extracts text (PDF via PyMuPDF/PaddleOCR-VL, .md/.txt read directly),
detects language, writes a staging_documents row, advances
raw_documents.raw_status to 'staged'.

Usage:
    python MAIN.py
"""
import os
import tempfile

from DB import get_connection
from MINIO_CLIENT import download_to_path
from LANG_DETECT import detect_language
from PARSERS.PDF import parse_pdf


def extract_text(local_path: str, filetype: str) -> tuple[str, bool]:
    """Returns (text, ocr_used)."""
    if filetype == "pdf":
        return parse_pdf(local_path)
    if filetype in ("md", "txt"):
        with open(local_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(), False
    raise ValueError(f"Unsupported filetype: {filetype}")


def run():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, original_filename, storage_key, filetype FROM raw_documents WHERE raw_status = 'received'"
    )
    pending = cur.fetchall()
    print(f"Found {len(pending)} document(s) pending staging.")

    for doc_id, filename, storage_key, filetype in pending:
        doc_id_str = str(doc_id)
        print(f"[{doc_id_str}] downloading '{filename}' from MinIO ...")

        with tempfile.TemporaryDirectory() as tmp_dir:
            local_path = os.path.join(tmp_dir, filename)
            try:
                download_to_path(storage_key, local_path)
                text, ocr_used = extract_text(local_path, filetype)
            except Exception as e:
                print(f"[{doc_id_str}] FAILED: {e}")
                cur.execute(
                    "UPDATE raw_documents SET raw_status = 'failed' WHERE id = %s",
                    (doc_id_str,),
                )
                conn.commit()
                continue

        language = detect_language(text)
        print(f"[{doc_id_str}] extracted {len(text)} chars, ocr_used={ocr_used}, language={language}")

        cur.execute(
            """
            INSERT INTO staging_documents
                (raw_document_id, extracted_text, ocr_used, language, staging_status)
            VALUES (%s, %s, %s, %s, 'staged')
            """,
            (doc_id_str, text, ocr_used, language),
        )
        cur.execute(
            "UPDATE raw_documents SET raw_status = 'staged' WHERE id = %s",
            (doc_id_str,),
        )
        conn.commit()
        print(f"[{doc_id_str}] staged.")

    cur.close()
    conn.close()
    print("Done. Next: classification + translation + similarity-dedup (WAREHOUSE/INTERMEDIATE).")


if __name__ == "__main__":
    run()
