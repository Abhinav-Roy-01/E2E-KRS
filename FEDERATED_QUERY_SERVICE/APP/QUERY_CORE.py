"""
One question in, one fully-explained answer out.

Routing (cheapest and safest first):
  1. refused      -- input that is plainly SQL, not a question
  2. rules        -- known question shapes -> parameterized SQL template
  3. text_to_sql  -- "structured" questions the rules don't cover -> local
                     Qwen3 writes SQL -> validate_sql() -> read-only execute
  4. vector_rag   -- everything else -> bge-m3 similarity search over the
                     faculty context vectors -> Qwen3 answer that must cite
                     its sources as [S1], [S2]...

Structured answers (1-3) are built straight from the returned rows -- no LLM
paraphrase, so a number in the answer is always a number the database
returned. The LLM is only used where free text has to be summarised.
Everything the caller needs to verify the answer comes back with it: route,
exact SQL, parameters, rows, sources.
"""
import logging
import os
import re
import sys
from pathlib import Path

import requests

_AICTE = Path(__file__).resolve().parents[2] / "STRUCTURED_INTEGRATION" / "AICTE_PIPELINE"
for _sub in ("11_RETRIEVAL", "09_EMBEDDINGS", "10_PGVECTOR"):
    _p = str(_AICTE / _sub)
    if _p not in sys.path:
        sys.path.append(_p)

from QUERY_ROUTER import try_rules, generate_sql_via_llm, validate_sql  # noqa: E402
from HYBRID_RETRIEVER import classify_query_type  # noqa: E402
from EMBEDDING_GENERATOR import embed_texts  # noqa: E402
from VECTOR_STORE import similarity_search  # noqa: E402
from AICTE_DB import get_aicte_connection  # noqa: E402

log = logging.getLogger("query_core")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:8b")
MAX_ROWS = 50
TOP_K = 5

_MALICIOUS = re.compile(
    r";|--|\b(?:drop|truncate|alter)\s+(?:table|database)\b|\bdelete\s+from\b", re.I
)


def _empty_result(question: str) -> dict:
    return {
        "question": question, "route": None, "answer": "", "sql": None, "params": [],
        "columns": [], "rows": [], "truncated": False, "sources": [], "error": None,
    }


def _execute_select(conn, sql: str, params) -> tuple[list, list, bool]:
    with conn.cursor() as cur:
        # params=None (not ()) when there are none: psycopg would otherwise try to
        # interpret a literal % inside generated SQL, e.g. LIKE '%a%'.
        cur.execute(sql, params if params else None)
        columns = [d.name for d in cur.description]
        fetched = cur.fetchmany(MAX_ROWS + 1)
    truncated = len(fetched) > MAX_ROWS
    rows = [dict(zip(columns, r)) for r in fetched[:MAX_ROWS]]
    return columns, rows, truncated


def _answer_from_rows(columns: list, rows: list, truncated: bool) -> str:
    if not rows:
        return "No matching rows found."
    if len(rows) == 1 and len(columns) == 1:
        return f"{columns[0]}: {rows[0][columns[0]]}"
    note = f" (showing first {MAX_ROWS})" if truncated else ""
    return f"{len(rows)} row(s) returned{note}."


def _synthesize(question: str, sources: list) -> str:
    """Cited answer from retrieved sources. Falls back to listing the sources if Ollama is down."""
    tagged = "\n".join(f"[S{i}] {s['context_text']}" for i, s in enumerate(sources, 1))
    prompt = (
        "Answer the question using ONLY the sources below. After every fact, cite the source "
        "tag in square brackets, like [S1]. If the sources do not contain the answer, reply "
        "with exactly this sentence and nothing else: I could not find this in the available records. "
        "Never use outside knowledge.\n\n"
        f"QUESTION: {question}\n\nSOURCES:\n{tagged}\n\nANSWER:"
    )
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False,
                  "think": False, "keep_alive": "10m"},
            timeout=120,
        )
        resp.raise_for_status()
        text = re.sub(r"<think>.*?</think>", "", resp.json()["response"], flags=re.S).strip()
        return text or "The model returned an empty answer."
    except requests.RequestException as e:
        log.warning("Ollama unreachable for synthesis: %s", e)
        lines = [f"[S{i}] {s['context_text']}" for i, s in enumerate(sources, 1)]
        return "Language model unavailable; most relevant retrieved records:\n" + "\n".join(lines)


def run_query(question: str) -> dict:
    result = _empty_result(question)

    if _MALICIOUS.search(question):
        result.update(route="refused",
                      answer="Refused: the input contains SQL-like syntax and was not treated as a question.")
        return result

    conn = None
    try:
        rule = try_rules(question)
        qtype = classify_query_type(question)

        if rule or qtype == "structured":
            if rule:
                sql, params = rule
                result["route"] = "rules"
            else:
                sql, params = generate_sql_via_llm(question), ()
                result["route"] = "text_to_sql"
                if sql is None:
                    result.update(error="llm_unavailable",
                                  answer="The language model is unavailable, so this question could not be translated to SQL.")
                    return result

            result["sql"], result["params"] = sql, [str(p) for p in params]

            ok, reason = validate_sql(sql)
            if not ok:
                result.update(error="sql_rejected",
                              answer=f"The generated SQL was rejected and NOT executed: {reason}")
                return result

            conn = get_aicte_connection()
            cols, rows, truncated = _execute_select(conn, sql, params)
            result.update(columns=cols, rows=rows, truncated=truncated,
                          answer=_answer_from_rows(cols, rows, truncated))
            return result

        # vector_rag
        result["route"] = "vector_rag"
        conn = get_aicte_connection()
        embedding = embed_texts([question])[0]
        sources = similarity_search(conn, embedding, top_k=TOP_K)
        sources = [s for s in sources if float(s.get("similarity", 1)) >= 0.5]
        result["sources"] = sources
        result["answer"] = (_synthesize(question, sources) if sources
                            else "I could not find this in the available records.")
        return result

    except Exception as e:  # never leak internals to the client; full detail goes to the server log
        log.exception("query failed")
        result.update(error="internal_error",
                      answer=f"The query could not be completed ({type(e).__name__}).")
        return result
    finally:
        if conn is not None:
            conn.close()
