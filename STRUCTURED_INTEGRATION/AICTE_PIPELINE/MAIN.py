"""
MAIN — runs the pipeline end-to-end (ingest -> ... -> deduplication) against
sample data, so you always have a working thing to point at, even mid-build.
Phases 08-11 (Postgres load / embeddings / pgvector / retrieval) require a
live Postgres+pgvector instance and are called out explicitly below rather
than silently skipped.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for folder in ["01_INGESTION", "02_SCHEMA_DISCOVERY", "03_SCHEMA_MAPPING",
               "04_STANDARDIZATION", "05_NORMALIZATION", "06_DEDUPLICATION",
               "07_CONTEXT_CLASSIFICATION", "09_EMBEDDINGS"]:
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
from FIELD_CLASSIFIER import classify_columns
from CONTEXT_BUILDER import build_internship_context


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

    print("\n── 06b INTERNSHIP ID ASSIGNMENT ──────────────────────")
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

    print("\n── 09 CONTEXT BUILDING (sample) ──────────────────────")
    sample_context = build_internship_context(
        "Rahul Sharma", "IIT Delhi", "Google", "6-month", 2025,
        "Excellent performance, demonstrated strong ML and analytical skills",
    )
    print(f"  {sample_context}")

    print("\n── 08 / 10 / 11 (require live Postgres+pgvector) ─────")
    print("  Not run here — see 08_POSTGRESQL, 10_PGVECTOR, 11_RETRIEVAL")
    print("  once your .env DB settings point at a real instance.")

    print("\nPipeline run complete (sample data, phases 01-07 + 09 context-build).")


if __name__ == "__main__":
    run_pipeline()
