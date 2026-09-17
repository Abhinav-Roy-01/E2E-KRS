"""
pgvector-backed context store for the document arm. Replaces the earlier
Chroma client -- deliberately, not incidentally: AICTE_PIPELINE/10_PGVECTOR
already stores its context vectors in a Postgres `context_document` table.
Using the SAME table shape and the SAME embedding model (bge-m3, see
EMBEDDER.py) here means document-chunk vectors and AICTE-context vectors are
directly comparable, which is what makes one unified retrieval layer
possible instead of two separate RAG systems glued together after the fact.

This intentionally does NOT share a single physical database with AICTE's
own Postgres -- merging unrelated schemas into one DB is a bigger, riskier
change than this project's timeline supports. Instead: two databases, one
identical table shape, one shared embedding model. The retrieval layer
queries both and merges on equal footing (same embedding space => directly
comparable cosine similarity, no cross-space fusion trick needed).

`entity_type='document'` distinguishes document-arm rows from AICTE's own
institution/course/faculty/student rows if the two ever DO share a
database in some future deployment.
"""
import os

try:
    import psycopg
    from pgvector.psycopg import register_vector
except ImportError:
    psycopg = None

CREATE_CONTEXT_TABLE_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS context_document (
    context_id          SERIAL PRIMARY KEY,
    entity_id            TEXT NOT NULL,
    entity_type          TEXT NOT NULL,
    context_type         TEXT,
    context_text         TEXT NOT NULL,
    embedding            VECTOR(1024),  -- bge-m3 dimension, matches AICTE's context_document
    source_database      TEXT,
    source_table         TEXT,
    source_record_id     TEXT,
    confidence           REAL DEFAULT 1.0,
    created_at           TIMESTAMPTZ DEFAULT now(),
    updated_at           TIMESTAMPTZ DEFAULT now(),
    data_version         TEXT DEFAULT 'v1'
);
"""

# See AICTE's 10_PGVECTOR/VECTOR_STORE.py for the same ivfflat-on-empty-table
# caveat -- don't build this index until the table has hundreds+ of rows.
BUILD_VECTOR_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_context_embedding
    ON context_document USING ivfflat (embedding vector_cosine_ops);
"""


def build_vector_index(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(BUILD_VECTOR_INDEX_SQL)
    conn.commit()


def get_connection():
    if psycopg is None:
        raise RuntimeError("psycopg/pgvector not installed -- pip install -r REQUIREMENTS.TXT")
    conn = psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ.get("POSTGRES_DB", "ekrs"),
        user=os.environ.get("POSTGRES_USER", "ekrs"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
    )
    register_vector(conn)
    return conn


def insert_context(conn, entity_id: str, context_text: str, embedding: list[float],
                    entity_type: str = "document", context_type: str | None = None,
                    **lineage) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO context_document
                (entity_id, entity_type, context_type, context_text, embedding,
                 source_database, source_table, source_record_id)
            VALUES (%s, %s, %s, %s, %s::vector, %s, %s, %s)
            """,
            (entity_id, entity_type, context_type, context_text, embedding,
             lineage.get("source_database", "ekrs"), lineage.get("source_table", "vector_mart_chunks"),
             lineage.get("source_record_id")),
        )
    conn.commit()


def similarity_search(conn, query_embedding: list[float], top_k: int = 5) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT entity_id, entity_type, context_text,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM context_document
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (query_embedding, query_embedding, top_k),
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


if __name__ == "__main__":
    print("This script expects a live Postgres+pgvector connection (.env).")
    print("Run CREATE_CONTEXT_TABLE_SQL against your DB first, or apply")
    print("DATABASE/SCHEMA/005_VECTOR_MART.SQL which now includes it.")
