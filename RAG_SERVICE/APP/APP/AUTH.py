"""
Real, DB-backed identity + RBAC -- replaces the earlier single-shared-secret
API_KEY scheme (a static string compared byte-for-byte, no identity, no
role, no department, no audit trail behind it).

Every API key belongs to a real row in `users` (name, role, department).
Keys are never stored raw -- only their sha256 hash. The raw key is shown
exactly once, at creation time (see CREATE_USER.py), same as any real
provider (GitHub, Stripe, etc.) does it.

Usage in any service's MAIN.py:
    from AUTH import get_current_user
    @app.post("/ingest", dependencies=[Depends(get_current_user)])
    async def ingest(..., user: dict = Depends(get_current_user)):
        # user = {"id": ..., "name": ..., "role": ..., "department": ...}
"""
import hashlib
import os

from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()  # finds .env by walking up from cwd

try:
    from DB import get_connection
except ImportError:
    # Services that copy this file into their own APP/ dir already have a
    # sibling DB.py with the same get_connection() signature -- this import
    # resolves to theirs, not SECURITY_SERVICE's, when run from there.
    from DB import get_connection  # noqa: F811


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def get_current_user(x_api_key: str = Header(default="")) -> dict:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")

    key_hash = _hash_key(x_api_key)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, role, department FROM users WHERE api_key_hash = %s",
                (key_hash,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    return {"id": row[0], "name": row[1], "role": row[2], "department": row[3]}


def require_role(*allowed_roles: str):
    """
    Dependency factory for endpoints that need more than "any authenticated
    user" -- e.g. Depends(require_role("admin", "department_head")).
    Not used yet anywhere in this build (no endpoint needs it yet), but the
    real RBAC check -- once a query/routing endpoint exists -- is exactly
    this pattern: look up department_access_rules for (user.role, target
    document's department) and compare max_sensitivity_tier, not just "is
    this user authenticated at all."
    """
    from fastapi import Depends

    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Role '{user['role']}' cannot access this endpoint.")
        return user
    return _check
