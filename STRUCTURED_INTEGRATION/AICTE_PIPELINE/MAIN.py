"""
MAIN — runs the pipeline end-to-end. Phases 01-07 run against either sample
data or live sources (USE_SAMPLE_DATA in .env). Phases 08 (Postgres load)
and 09/10 (faculty context -> bge-m3 embedding -> pgvector) now actually run
against a live instance when USE_SAMPLE_DATA=false -- previously this was
three print statements saying "not run here." Institutions load via
DB_LOADER; faculty research_interests embed via EMBEDDING_PIPELINE. Course/
student/internship loading and internship-context embedding remain
deferred -- see STRUCTURED_INTEGRATION/README.MD for why (a real schema
mismatch, not just missing wiring).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for folder in ["01_INGESTION", "02_SCHEMA_DISCOVERY", "03_SCHEMA_MAPPING",
               "04_STANDARDIZATION", "05_NORMALIZATION", "06_DEDUPLICATION",
               "07_CONTEXT_CLASSIFICATION", "08_POSTGRESQL", "09_EMBEDDINGS", "10_PGVECTOR"]:
    sys.path.insert(0, str(ROOT / folder))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import pandas as pd
from INGESTION_ENGINE import ingest_all
from SCHEMA_DISCOVERY import discover_all
from SCHEMA_MAPPER import map_all
from STANDARDIZER import standardize_all
from NORMALIZER import normalize_all
from ENTITY_RESOLVER import match_entities, build_entity_mapping
from DATA_VALIDATOR import validate_institutions
from FIELD_CLASSIFIER import classify_columns
from CONTEXT_BUILDER import build_internship_context
import DB_LOADER
from EMBEDDING_PIPELINE import process_faculty_records


def run_pipeline():
    use_sample_data = str(os.getenv("USE_SAMPLE_DATA", "true")).strip().lower() == "true"
    sample_dir = ROOT / "DATA" / "SAMPLE" if use_sample_data else None

    print("── 01 INGESTION ──────────────────────────────────────")
    raw = ingest_all(sample_dir)
    for name, df in raw.items():
        print(f"  {name}: {len(df)} rows ingested")

    print("\n── 02 SCHEMA DISCOVERY ───────────────────────────────")
    profile = discover_all(raw)
    print(f"  {len(profile)} fields profiled across all sources")

    print("\n── 03 SCHEMA MAPPING ─────────────────────────────────")
    mapped = map_all(raw)
    print(f"  fields mapped to canonical names for {len(mapped)} sources")

    print("\n── 04 STANDARDIZATION ────────────────────────────────")
    standardized = standardize_all(mapped)
    print("  states / booleans / text normalized")

    print("\n── 05 NORMALIZATION ──────────────────────────────────")
    normalized = normalize_all(standardized)
    print("  dtypes cast to canonical schema")

    print("\n── 06 ENTITY RESOLUTION ──────────────────────────────")
    combined = pd.concat(normalized.values(), ignore_index=True)
    resolved = match_entities(combined)
    entity_map = build_entity_mapping(resolved)
    n_unique = resolved["master_entity_id"].nunique()
    print(f"  {len(resolved)} source records -> {n_unique} master entities")
    print(entity_map.to_string(index=False))

    print("\n── 06b DATA VALIDATION ────────────────────────────────")
    valid_institutions, rejected_institutions = validate_institutions(resolved)
    print(f"  {len(valid_institutions)} valid, {len(rejected_institutions)} rejected")
    if not rejected_institutions.empty:
        print(rejected_institutions[["institution_name", "rejection_reason"]].to_string(index=False))

    print("\n── 06c INTERNSHIP ID ASSIGNMENT ──────────────────────")
    from ENTITY_RESOLVER import assign_internship_ids, extract_internship_rows
    internships_df = extract_internship_rows(combined)
    if not internships_df.empty and "internship_year" in internships_df.columns:
        internships_df["internship_year"] = internships_df["internship_year"].astype(int)
    internships_df = assign_internship_ids(internships_df)
    print(f"  {len(internships_df)} internship rows -> {internships_df['internship_id'].nunique() if 'internship_id' in internships_df.columns else 0} unique internships")
    if not internships_df.empty:
        print(internships_df[["internship_id", "student_name", "company", "internship_year"]].to_string(index=False))
    else:
        print("  No internship rows available in this source schema; continuing without internship assignment.")


    print("\n── 07 CONTEXT CLASSIFICATION ─────────────────────────")
    classification = classify_columns(list(combined.columns))
    contextual_fields = [f for f, t in classification.items() if t == "contextual"]
    print(f"  contextual fields flagged for embedding: {contextual_fields}")

    print("\n── 09a CONTEXT_BUILDER DEMO (illustrative, not the real load) ──")
    sample_context = build_internship_context(
        "Rahul Sharma", "IIT Delhi", "Google", "6-month", 2025,
        "Excellent performance, demonstrated strong ML and analytical skills",
    )
    print(f"  {sample_context}")

    print("\n── 08 / 09 / 10: CANONICAL LOAD + FACULTY EMBEDDINGS ──")
    if use_sample_data:
        print("  Skipped -- sample data has no real DB-backed lineage to load.")
        print("  Set USE_SAMPLE_DATA=false to run this against a live instance.")
    else:
        try:
            conn = DB_LOADER.get_connection()
            DB_LOADER.load_all(conn, valid_institutions)
            conn.close()
            print(f"  Loaded {valid_institutions['master_entity_id'].nunique()} institutions into Postgres.")
        except Exception as e:
            print(f"  Postgres load skipped -- {e}")
            print("  (check POSTGRES_HOST/PORT/DB/USER/PASSWORD in .env)")

        faculty_rows = resolved[resolved.get("research_interests").notna()] if "research_interests" in resolved.columns else resolved.iloc[0:0]
        if faculty_rows.empty:
            print("  No faculty rows with research_interests in this source data -- nothing to embed.")
        else:
            try:
                process_faculty_records(faculty_rows)
            except Exception as e:
                print(f"  Faculty embedding skipped -- {e}")
                print("  (check OLLAMA_URL is reachable and `ollama pull bge-m3` has been run)")

    print("\n── 11 RETRIEVAL ────────────────────────────────────────")
    print("  Not run here -- see 11_RETRIEVAL/HYBRID_RETRIEVER.py; this is")
    print("  a query-time module, not part of the ingest-to-canonical pipeline.")

    print("\nPipeline run complete "
          f"({'sample data' if use_sample_data else 'LIVE data'}, phases 01-07 + 09-10).")


if __name__ == "__main__":
    run_pipeline()
