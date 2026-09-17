"""
Minimal API-key auth dependency, shared pattern across every FastAPI
service in this project. Full RBAC (role/department/sensitivity-tier
checks against DATABASE/SCHEMA/006_SECURITY.SQL's users and
department_access_rules tables) is deliberately NOT built here -- that's
scheduled as dedicated follow-up work, not something to bolt on inside a
scaffolding pass. This gives every endpoint a real "who's allowed to call
this at all" gate in the meantime, which is a large step up from zero.

Usage in any service's MAIN.py:
    from AUTH import require_api_key
    @app.post("/ingest", dependencies=[Depends(require_api_key)])
"""
import os

from fastapi import Header, HTTPException

API_KEY = os.environ.get("API_KEY", "")


async def require_api_key(x_api_key: str = Header(default="")):
    if not API_KEY or API_KEY == "changeme_generate_a_real_key":
        raise HTTPException(
            status_code=500,
            detail="API_KEY is not configured on the server -- set a real value in .env before exposing this endpoint.",
        )
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header.")
