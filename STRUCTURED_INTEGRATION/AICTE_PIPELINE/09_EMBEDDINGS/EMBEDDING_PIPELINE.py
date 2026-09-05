"""
09_EMBEDDINGS — glue script: contextual fields -> context text -> embedding -> pgvector.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "10_PGVECTOR"))

from CONTEXT_BUILDER import build_internship_context
from EMBEDDING_GENERATOR import embed_texts
from VECTOR_STORE import get_connection, insert_context


def process_internship_records(internships_df):
    """
    Takes a dataframe of internship rows (student_name, institution_name,
    company, duration, internship_year, performance_remark + lineage cols)
    and pushes each one into pgvector as a context document.
    """
    conn = get_connection()

    for _, row in internships_df.iterrows():
        # 1. Build rich context text (not just the raw remark — see design doc Section 6)
        context_text = build_internship_context(
            row["student_name"], row["institution_name"], row["company"],
            row["duration"], row["internship_year"], row["performance_remark"],
        )

        # 2. Embed it (embed_texts takes/returns a LIST, so we wrap/unwrap a single item)
        embedding = embed_texts([context_text])[0]

        # 3. Write it to pgvector, tagged with what it is and where it traces back to
        insert_context(
            conn,
            entity_id=row["internship_id"],       # the pk from CANONICAL_SCHEMA.yaml
            entity_type="internship",               # what kind of entity this describes
            context_type="performance_remark",       # what kind of context this is
            context_text=context_text,
            embedding=embedding,
            source_database=row.get("source_database"),
            source_table=row.get("source_table"),
            source_record_id=row.get("source_record_id"),
        )

    conn.close()
    print(f"Loaded {len(internships_df)} internship context documents into pgvector.")


if __name__ == "__main__":
    print("This script expects a live Postgres+pgvector connection (.env) "
          "and an internships_df with columns: student_name, institution_name, "
          "company, duration, internship_year, performance_remark, internship_id "
          "(+ lineage columns). Call process_internship_records(df) with that.")