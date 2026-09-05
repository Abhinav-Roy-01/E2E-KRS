"""
DuckDB is used ONLY for analytics dashboard queries — document volume trends,
department load, compliance status over time. It is NOT the source of truth
(that's still Postgres) and NOT a general-purpose data warehouse.

Why DuckDB here specifically: it's an embedded, columnar OLAP engine — fast at
exactly this kind of aggregation query — without needing to run it as its own
service. It reads Postgres directly via the postgres_scanner extension, so there's
no separate ETL/sync step to maintain; DuckDB always sees live data.

Usage (Phase 9 — analytics dashboard, not needed before then):
    from analytics_queries import get_document_volume_by_department
    rows = get_document_volume_by_department()
"""
import duckdb

POSTGRES_CONN = "host=localhost port=5432 dbname=ekrs user=ekrs password=ekrs_dev_password"


def _connect():
    con = duckdb.connect(database=":memory:")
    con.execute("INSTALL postgres;")
    con.execute("LOAD postgres;")
    con.execute(f"ATTACH '{POSTGRES_CONN}' AS pg (TYPE postgres, READ_ONLY);")
    return con


def get_document_volume_by_department():
    con = _connect()
    result = con.execute(
        """
        SELECT department, COUNT(*) AS doc_count
        FROM pg.documents
        WHERE department IS NOT NULL
        GROUP BY department
        ORDER BY doc_count DESC
        """
    ).fetchall()
    con.close()
    return result


def get_documents_over_time(bucket: str = "week"):
    """bucket: 'day' | 'week' | 'month'"""
    con = _connect()
    result = con.execute(
        f"""
        SELECT date_trunc('{bucket}', upload_date) AS period, COUNT(*) AS doc_count
        FROM pg.documents
        GROUP BY period
        ORDER BY period
        """
    ).fetchall()
    con.close()
    return result


def get_compliance_status_summary():
    con = _connect()
    result = con.execute(
        """
        SELECT status, COUNT(*) AS flag_count
        FROM pg.compliance_flags
        GROUP BY status
        """
    ).fetchall()
    con.close()
    return result
