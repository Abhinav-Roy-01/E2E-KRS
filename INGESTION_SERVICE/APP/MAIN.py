"""
INGESTION_SERVICE — the actual entry point for the document arm.

Computes a SHA-256 hash of the incoming file BEFORE storing anything.
If a document with the same hash already exists in raw_documents, this is
an exact duplicate — flag it and skip storage entirely, rather than
creating a second copy that WAREHOUSE/STAGING would have to process again.
This is the cheap, first-pass dedup check (see architecture doc) — the
more expensive similarity-based check for near-duplicates happens later,
in WAREHOUSE/INTERMEDIATE, after text has actually been extracted.
"""
import hashlib
import uuid

from fastapi import Depends, FastAPI, UploadFile, File, HTTPException
from AUTH import require_api_key
from STORAGE import upload_file, ensure_bucket
from DB import get_connection

app = FastAPI(title="E2E-KRS Ingestion Service")

# Every source (folder watch, WhatsApp, future email) funnels through this
# one filetype allow-list -- reject anything else before it's stored, not
# after. Extend this list, not the endpoint logic, when adding a filetype.
ALLOWED_FILETYPES = {"pdf", "md", "txt", "jpg", "jpeg", "png"}


@app.on_event("startup")
async def startup():
    ensure_bucket()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ingest", dependencies=[Depends(require_api_key)])
async def ingest(file: UploadFile = File(...), source: str = "manual_upload"):
    filetype = file.filename.split(".")[-1].lower()
    if filetype not in ALLOWED_FILETYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported filetype: {filetype}")

    file_bytes = await file.read()
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    conn = get_connection()
    cur = conn.cursor()

    # Exact-duplicate check, before anything gets stored.
    cur.execute(
        "SELECT id, original_filename FROM raw_documents WHERE sha256_hash = %s",
        (sha256_hash,),
    )
    existing = cur.fetchone()
    if existing:
        cur.close()
        conn.close()
        return {
            "status": "duplicate_exact",
            "message": f"Identical file already ingested as '{existing[1]}'",
            "existing_id": str(existing[0]),
        }

    doc_id = uuid.uuid4()
    object_key = str(doc_id)
    upload_file(object_key, file_bytes, content_type=file.content_type or "application/octet-stream")

    cur.execute(
        """
        INSERT INTO raw_documents
            (id, source, original_filename, storage_key, sha256_hash, filetype, raw_status)
        VALUES (%s, %s, %s, %s, %s, %s, 'received')
        """,
        (str(doc_id), source, file.filename, object_key, sha256_hash, filetype),
    )
    conn.commit()
    cur.close()
    conn.close()

    return {"status": "received", "id": str(doc_id), "filename": file.filename}
