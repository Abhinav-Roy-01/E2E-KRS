r"""
FEDERATED_QUERY_SERVICE -- the one HTTP entry point for natural-language
questions over the AICTE data.

  POST /query   {"question": "..."}   header: X-API-Key
  GET  /health

Every /query call is authenticated as a real user, rate-limited per user,
and written to audit_log (question, route, exact SQL) BEFORE the answer is
returned -- if the audit write fails the answer is withheld (fail closed),
so there is no such thing as an unlogged answer.

Run (from this APP folder):
    ..\.venv\Scripts\python.exe -m uvicorn MAIN:app --port 8001
"""
from dotenv import load_dotenv
load_dotenv()  # must run before QUERY_CORE import: its dependencies read env at import time

import json
import os
import time
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from AUTH import get_current_user
from DB import get_connection
from QUERY_CORE import run_query

app = FastAPI(title="E2E-KRS Federated Query Service")

_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:8001,http://127.0.0.1:8001,http://localhost:5500,http://127.0.0.1:5500",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)

# Per-user sliding window. In-process memory: fine for one server process and a
# demo; for real deployment move this to Redis (already in DOCKER-COMPOSE.YML).
RATE_LIMIT = int(os.environ.get("QUERY_RATE_LIMIT_PER_MIN", "30"))
_hits: dict = defaultdict(deque)


def _check_rate_limit(user_id: str) -> None:
    now = time.monotonic()
    window = _hits[user_id]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded -- try again in a minute.",
                            headers={"Retry-After": "60"})
    window.append(now)


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


def _write_audit(user: dict, question: str, result: dict) -> None:
    detail = json.dumps({"q": question[:300], "route": result["route"], "sql": result["sql"]})
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (user_id, document_mart_id, action, detail) VALUES (%s, NULL, 'query', %s)",
                (str(user["id"]), detail),
            )
        conn.commit()
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query")
def query(req: QueryRequest, user: dict = Depends(get_current_user)):
    _check_rate_limit(str(user["id"]))
    started = time.monotonic()
    result = run_query(req.question.strip())
    try:
        _write_audit(user, req.question, result)
    except Exception:
        raise HTTPException(status_code=500, detail="Audit log unavailable -- answer withheld.")
    result["elapsed_ms"] = int((time.monotonic() - started) * 1000)
    return result



import os
from fastapi.staticfiles import StaticFiles
app.mount("/ui", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "UI"), html=True), name="ui")