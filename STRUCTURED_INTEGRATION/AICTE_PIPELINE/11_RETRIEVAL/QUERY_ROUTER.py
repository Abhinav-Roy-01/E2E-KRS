"""
Query Router -- Rules -> SQL -> Vector -> Hybrid, exactly as drawn in the
architecture diagram. This module owns the "Rules -> SQL" half: known
question patterns hit a parameterized SQL template first (fast, free,
100% predictable); only what rules don't cover falls through to
LLM-generated text-to-SQL, which then passes through a hard validator
before anything runs.

Scoped to the `institution` table only. `course`/`faculty`/`student`/
`internship` tables are not yet populated with real rows (see
08_POSTGRESQL/DB_LOADER.py's own TODO) -- faculty context text lives in
pgvector's context_document, not the relational `faculty` table, so a
SQL query against `faculty` would silently return nothing. Extending this
router to those tables is real future work, not done here, because it
would need DB_LOADER wired for them first.
"""
import os
import re

import requests

try:
    import sqlglot
    from sqlglot import exp
except ImportError:
    sqlglot = None

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:8b")

ALLOWED_TABLES = {"institution"}

INSTITUTION_SCHEMA = """
Table: institution
  institution_id    TEXT (primary key)
  institution_name  TEXT
  state             TEXT
  approval_status   BOOLEAN
  nirf_rank         INTEGER
  naac_grade        TEXT
"""

# ── Rules branch — checked first, in order. Each is (regex, sql, param groups). ──
# Every pattern is anchored with ^ -- an unanchored search() lets a rule fire on
# a phrase buried mid-sentence ("How many institutes have a NAAC grade of A?"
# used to hit the "naac grade of <name>" rule and treat "A" as an institute
# name). A rule should only fire when the question IS that shape.
_LEAD = r"^(?:what(?:'s| is)\s+)?(?:the\s+)?"

RULES = [
    (
        re.compile(r"^how many (?:approved )?institut(?:es?|ions?) (?:are there )?in ([\w\s]+?)\??$", re.I),
        "SELECT COUNT(*) AS count FROM institution WHERE state ILIKE %s",
        1,
    ),
    (
        re.compile(r"^how many institut(?:es?|ions?) (?:are there)?\??$", re.I),
        "SELECT COUNT(*) AS count FROM institution",
        0,
    ),
    (
        re.compile(r"^list (?:all )?institut(?:es?|ions?) in ([\w\s]+?)\??$", re.I),
        "SELECT institution_name FROM institution WHERE state ILIKE %s LIMIT 20",
        1,
    ),
    (
        re.compile(_LEAD + r"(?:nirf\s+)?rank of ([\w\s.,'-]+?)\??$", re.I),
        "SELECT institution_name, nirf_rank FROM institution WHERE institution_name ILIKE %s LIMIT 5",
        1,
    ),
    (
        re.compile(_LEAD + r"naac grade of ([\w\s.,'-]+?)\??$", re.I),
        "SELECT institution_name, naac_grade FROM institution WHERE institution_name ILIKE %s LIMIT 5",
        1,
    ),
]


def try_rules(question: str):
    """Returns (sql, params) if a rule matches, else None."""
    q = question.strip()
    for pattern, sql, n_groups in RULES:
        m = pattern.search(q)
        if m:
            if n_groups == 0:
                return sql, ()
            arg = m.group(1).strip()
            return sql, (f"%{arg}%",)
    return None


def generate_sql_via_llm(question: str) -> str | None:
    """
    Text-to-SQL fallback for whatever the rules branch doesn't cover.
    Local Qwen3:8B only, same as every other LLM call in this project --
    the generated SQL is untrusted output either way and MUST pass
    validate_sql() before it ever touches a real connection.
    """
    prompt = (
        f"Generate a single PostgreSQL SELECT statement to answer this question.\n"
        f"Use ONLY this table, no others:\n{INSTITUTION_SCHEMA}\n"
        f"Rules: SELECT only. No other tables. No semicolons. No comments. "
        f"Output ONLY the SQL, nothing else.\n\n"
        f"Question: {question}\nSQL:"
    )
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False,
                  "think": False,  # Qwen3 otherwise burns most of the timeout on hidden reasoning
                  "keep_alive": "10m"},
            timeout=120,
        )
        response.raise_for_status()
        sql = response.json()["response"].strip()
        sql = re.sub(r"<think>.*?</think>", "", sql, flags=re.S).strip()
        # Models routinely wrap SQL in markdown fences despite instructions -- strip them.
        sql = re.sub(r"^```(?:sql)?\s*|\s*```$", "", sql, flags=re.I | re.M).strip()
        return sql
    except requests.RequestException as e:
        print(f"[generate_sql_via_llm] Ollama unreachable -- {e}")
        return None


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Hard validator -- both the rules branch's templates AND any
    LLM-generated SQL pass through here before execution. Returns
    (is_valid, reason). A rule-branch template can never fail this (it's
    hardcoded and reviewed), but running it through the same check keeps
    one code path instead of two, which is one fewer place to get wrong.
    """
    if sqlglot is None:
        return False, "sqlglot not installed -- cannot safely validate SQL, refusing to execute"

    if ";" in sql.rstrip(";"):
        return False, "multiple statements are not allowed"

    try:
        parsed = sqlglot.parse(sql, read="postgres")
    except Exception as e:
        return False, f"could not parse SQL: {e}"

    if len(parsed) != 1 or parsed[0] is None:
        return False, "expected exactly one statement"

    statement = parsed[0]
    if not isinstance(statement, exp.Select):
        return False, "only SELECT statements are allowed"

    tables = {t.name.lower() for t in statement.find_all(exp.Table)}
    disallowed = tables - ALLOWED_TABLES
    if disallowed:
        return False, f"query touches table(s) not on the allow-list: {disallowed}"

    return True, "ok"


def execute_validated_query(sql: str, params: tuple = ()) -> str:
    """Runs a query that has ALREADY passed validate_sql() -- never call this directly on raw input."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "10_PGVECTOR"))
    from VECTOR_STORE import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return "No matching rows found."
    return "; ".join(
        ", ".join(f"{col}={val}" for col, val in zip(cols, row))
        for row in rows[:20]
    )


_OBVIOUSLY_MALICIOUS = re.compile(
    r";|--|\b(?:drop|truncate|alter)\s+(?:table|database)\b|\bdelete\s+from\b",
    re.I,
)


def answer_structured(question: str) -> str:
    """
    The full Rules -> SQL pipeline for one question: try rules first, fall
    back to LLM text-to-SQL, validate whichever produced a query, execute
    only if valid, and always return a string (never raise) so the caller
    (HYBRID_RETRIEVER.run_structured_query) can hand it straight to
    synthesis without special-casing failure.
    """
    # Defense in depth: validate_sql() is the real guard, but there is no
    # reason to spend a slow LLM call generating SQL for input that is plainly
    # an injection attempt rather than a question.
    if _OBVIOUSLY_MALICIOUS.search(question):
        return "[refused: input contains SQL-like syntax and was not treated as a question]"

    rule_match = try_rules(question)
    if rule_match:
        sql, params = rule_match
        is_valid, reason = validate_sql(sql)
        if not is_valid:
            return f"[internal error: a rule-branch template failed validation -- {reason}]"
        try:
            return execute_validated_query(sql, params)
        except Exception as e:
            return f"[structured query failed to execute: {e}]"

    generated_sql = generate_sql_via_llm(question)
    if generated_sql is None:
        return "[structured retrieval unavailable -- Ollama unreachable]"

    is_valid, reason = validate_sql(generated_sql)
    if not is_valid:
        return f"[could not safely answer from structured data -- generated SQL rejected: {reason}]"

    try:
        return execute_validated_query(generated_sql)
    except Exception as e:
        return f"[structured query failed to execute: {e}]"


if __name__ == "__main__":
    for q in [
        "How many institutes are there?",
        "How many institutes in Karnataka?",
        "List institutes in Kerala",
        "What is the nirf rank of IIT Delhi?",
        "; DROP TABLE institution; --",
    ]:
        print(f"\nQ: {q}")
        rule = try_rules(q)
        print(f"  matched rule: {bool(rule)}")
        if not rule:
            print("  -> would fall through to text-to-SQL")
