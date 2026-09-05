"""
10_PGVECTOR — persist context_text + embedding + entity metadata into the
CONTEXT_DOCUMENT table (lives inside PostgreSQL via the pgvector extension —
see 08_POSTGRESQL/DATABASE_SCHEMA.sql for the CREATE EXTENSION line).
"""
import os

try:
    import psycopg
    from pgvector.psycopg import register_vector
except ImportError:
    psycopg = None

CREATE_CONTEXT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS context_document (
    context_id          SERIAL PRIMARY KEY,
    entity_id             TEXT NOT NULL,
    entity_type            TEXT NOT NULL,
    context_type           TEXT,
    context_text           TEXT NOT NULL,
    embedding                VECTOR(768),
    source_database          TEXT,
    source_table              TEXT,
    source_record_id          TEXT,
    confidence                 REAL DEFAULT 1.0,
    created_at                  TIMESTAMPTZ DEFAULT now(),
    updated_at                  TIMESTAMPTZ DEFAULT now(),
    data_version                  TEXT DEFAULT 'v1'
);
"""

# NOTE: an ivfflat index built on an empty (or near-empty) table is broken —
# it silently returns zero rows for index-driven queries even after you
# insert real data later (this bit us once already). Don't call this until
# the table has a meaningful number of rows (hundreds+); for small tables a
# full scan is instant and no index is needed at all.
BUILD_VECTOR_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_context_embedding
    ON context_document USING ivfflat (embedding vector_cosine_ops);
"""


def build_vector_index(conn) -> None:
    """Call this explicitly once the table has meaningful data volume."""
    with conn.cursor() as cur:
        cur.execute(BUILD_VECTOR_INDEX_SQL)
    conn.commit()


def get_connection():
    if psycopg is None:
        raise RuntimeError("psycopg/pgvector not installed — pip install -r REQUIREMENTS/REQUIREMENTS.txt")
    conn = psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "aicte_canonical"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )
    register_vector(conn)
    return conn


def insert_context(conn, entity_id: str, entity_type: str, context_type: str,
                    context_text: str, embedding: list[float], **lineage) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO context_document
                (entity_id, entity_type, context_type, context_text, embedding,
                 source_database, source_table, source_record_id)
            VALUES (%s, %s, %s, %s, %s::vector, %s, %s, %s)
            """,
            (entity_id, entity_type, context_type, context_text, embedding,
             lineage.get("source_database"), lineage.get("source_table"), lineage.get("source_record_id")),
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
    print("Run CREATE_CONTEXT_TABLE_SQL against your DB first.")