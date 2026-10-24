"""
DB-backed identity for this service -- same scheme as INGESTION_SERVICE:
every API key belongs to a real row in `users`, only its sha256 hash is
stored, and the caller's name/role/department come back with the request.
Synchronous on purpose: FastAPI runs sync dependencies in a threadpool, so
the blocking DB lookup doesn't stall the event loop.
"""
import hashlib

from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()

from DB import get_connection  # noqa: E402


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def get_current_user(x_api_key: str = Header(default="")) -> dict:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, role, department FROM users WHERE api_key_hash = %s",
                (_hash_key(x_api_key),),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    return {"id": row[0], "name": row[1], "role": row[2], "department": row[3]}
