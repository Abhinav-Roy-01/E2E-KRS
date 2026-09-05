"""
08_POSTGRESQL — load resolved, classified structured/relational data into
PostgreSQL. Run DATABASE_SCHEMA.sql once first (psql -f DATABASE_SCHEMA.sql).

Every upsert here is paired with an entity_mapping + data_lineage row —
that pairing is not optional decoration, it's what makes every answer
traceable back to its source record (design doc Rule 4).
"""
import os

import pandas as pd

try:
    import psycopg
except ImportError:
    psycopg = None  # allows dry-run / unit tests without a live DB


def get_connection():
    if psycopg is None:
        raise RuntimeError("psycopg not installed — pip install -r REQUIREMENTS/REQUIREMENTS.txt")
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "aicte_canonical"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


# ── lineage helpers ──────────────────────────────────────────────────────

def _record_entity_mapping(conn, master_entity_id: str, entity_type: str, row: pd.Series) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO entity_mapping
                (master_entity_id, entity_type, source_system, source_database,
                 source_table, source_record_id, match_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (master_entity_id, entity_type, row.get("source_system"), row.get("source_database"),
             row.get("source_table"), row.get("source_record_id"), row.get("match_score", 1.0)),
        )


def _record_lineage(conn, canonical_entity_id: str, row: pd.Series) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO data_lineage
                (canonical_entity_id, source_system, source_database, source_table,
                 source_record_id, ingestion_timestamp, validation_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (canonical_entity_id, row.get("source_system"), row.get("source_database"),
             row.get("source_table"), row.get("source_record_id"),
             row.get("ingestion_timestamp"), "loaded"),
        )


# ── entity loaders ───────────────────────────────────────────────────────

def upsert_institutions(conn, institutions_df: pd.DataFrame) -> None:
    for _, row in institutions_df.drop_duplicates("master_entity_id").iterrows():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO institution (institution_id, institution_name, state, approval_status,
                                          nirf_rank, naac_grade)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (institution_id) DO UPDATE
                SET institution_name = EXCLUDED.institution_name,
                    state = EXCLUDED.state,
                    approval_status = COALESCE(EXCLUDED.approval_status, institution.approval_status),
                    nirf_rank = COALESCE(EXCLUDED.nirf_rank, institution.nirf_rank),
                    naac_grade = COALESCE(EXCLUDED.naac_grade, institution.naac_grade)
                """,
                (row["master_entity_id"], row["institution_name"], row.get("state"),
                 row.get("approval_status"), row.get("nirf_rank"), row.get("naac_grade")),
            )
        _record_entity_mapping(conn, row["master_entity_id"], "institution", row)
        _record_lineage(conn, row["master_entity_id"], row)
    conn.commit()


def upsert_courses(conn, courses_df: pd.DataFrame) -> None:
    for _, row in courses_df.drop_duplicates("course_id").iterrows():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO course (course_id, institution_id, course_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (course_id) DO UPDATE
                SET course_name = EXCLUDED.course_name,
                    institution_id = EXCLUDED.institution_id
                """,
                (row["course_id"], row["institution_id"], row["course_name"]),
            )
        _record_entity_mapping(conn, row["course_id"], "course", row)
        _record_lineage(conn, row["course_id"], row)
    conn.commit()


def upsert_faculty(conn, faculty_df: pd.DataFrame) -> None:
    for _, row in faculty_df.drop_duplicates("faculty_id").iterrows():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO faculty (faculty_id, institution_id, faculty_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (faculty_id) DO UPDATE
                SET faculty_name = EXCLUDED.faculty_name,
                    institution_id = EXCLUDED.institution_id
                """,
                (row["faculty_id"], row["institution_id"], row["faculty_name"]),
            )
        _record_entity_mapping(conn, row["faculty_id"], "faculty", row)
        _record_lineage(conn, row["faculty_id"], row)
    conn.commit()

    # NOTE: research_interests is contextual — it is NOT inserted here.
    # It goes to 10_PGVECTOR via 09_EMBEDDINGS instead (see design doc Section 4C).


def upsert_students(conn, students_df: pd.DataFrame) -> None:
    for _, row in students_df.drop_duplicates("student_id").iterrows():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO student (student_id, institution_id, student_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (student_id) DO UPDATE
                SET student_name = EXCLUDED.student_name,
                    institution_id = EXCLUDED.institution_id
                """,
                (row["student_id"], row["institution_id"], row["student_name"]),
            )
        _record_entity_mapping(conn, row["student_id"], "student", row)
        _record_lineage(conn, row["student_id"], row)
    conn.commit()


def upsert_internships(conn, internships_df: pd.DataFrame) -> None:
    for _, row in internships_df.drop_duplicates("internship_id").iterrows():
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO internship (internship_id, student_id, company, duration, internship_year)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (internship_id) DO UPDATE
                SET company = EXCLUDED.company,
                    duration = EXCLUDED.duration,
                    internship_year = EXCLUDED.internship_year
                """,
                (row["internship_id"], row["student_id"], row.get("company"),
                 row.get("duration"), row.get("internship_year")),
            )
        _record_entity_mapping(conn, row["internship_id"], "internship", row)
        _record_lineage(conn, row["internship_id"], row)
    conn.commit()

    # NOTE: performance_remark is contextual — NOT inserted here.
    # It goes to 10_PGVECTOR via 09_EMBEDDINGS/CONTEXT_BUILDER.py instead.


def load_all(conn, resolved_df: pd.DataFrame) -> None:
    """
    Convenience entrypoint: given the entity-resolved dataframe from
    06_DEDUPLICATION, load whichever tables have the right columns present.
    Extend this as more entity types flow through the pipeline.
    """
    if "master_entity_id" in resolved_df.columns and "institution_name" in resolved_df.columns:
        upsert_institutions(conn, resolved_df)
    # TODO: once course/faculty/student/internship dataframes exist as their
    # own entity-resolved frames (not just columns bolted onto institution
    # rows), call upsert_courses / upsert_faculty / upsert_students /
    # upsert_internships here too.


if __name__ == "__main__":
    print("This script expects a live Postgres connection (.env). "
          "Run DATABASE_SCHEMA.sql first, then call load_all() "
          "with the entity-resolved dataframe from 06_DEDUPLICATION.")
