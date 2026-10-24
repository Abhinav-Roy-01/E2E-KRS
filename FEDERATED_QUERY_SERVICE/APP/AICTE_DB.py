"""
Connection to the AICTE canonical database (institution table + faculty
context vectors). Deliberately NOT built on the AICTE pipeline's
VECTOR_STORE.get_connection(): that reads POSTGRES_* env vars, and the root
.env uses the very same names for the *document* database (port 5432). Reusing
it here would silently point AICTE questions at the wrong database.

Every connection from here is READ-ONLY at the server level and has a hard
statement timeout. validate_sql() already restricts generated SQL to a
single SELECT on an allow-listed table; this is the second, independent
layer, so even a validator bug cannot turn into a write or a runaway query.
(Production hardening on top of this: a dedicated DB role with SELECT-only
grants on `institution` and `context_document`.)
"""
import os

import psycopg
from pgvector.psycopg import register_vector


def get_aicte_connection():
    password = os.environ.get("AICTE_DB_PASSWORD", "")
    if not password:
        raise RuntimeError("AICTE_DB_PASSWORD is not set -- add the AICTE_DB_* lines to .env")
    conn = psycopg.connect(
        host=os.environ.get("AICTE_DB_HOST", "localhost"),
        port=os.environ.get("AICTE_DB_PORT", "55432"),
        dbname=os.environ.get("AICTE_DB_NAME", "aicte_canonical"),
        user=os.environ.get("AICTE_DB_USER", "postgres"),
        password=password,
        connect_timeout=5,
        options="-c default_transaction_read_only=on -c statement_timeout=8000",
    )
    register_vector(conn)
    return conn
