"""
06_DEDUPLICATION — resolve "IIT Delhi" / "IIT-D" / "Indian Institute of
Technology, Delhi" into one canonical entity ID.

MVP: a lightweight rule-based matcher (normalized-name blocking + token
overlap) — good enough to prove the pipeline end-to-end on sample data.
Swap `match_entities` for a Splink `Linker` (see splink.readthedocs.io) once
volumes/ambiguity justify probabilistic matching — the match_threshold and
blocking_fields are already externalized in 13_CONFIG/CONFIG.yaml for that.
"""
import re
from pathlib import Path

import pandas as pd
import yaml

CONFIG_PATH = Path(__file__).resolve().parents[1] / "13_CONFIG" / "CONFIG.yaml"


def _normalize_name(name: str | object) -> str:
    if pd.isna(name):
        return ""
    name = str(name)
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", " ", name)          # strip punctuation (IIT-D -> iit d)
    name = re.sub(r"\b(indian institute of technology|iit)\b", "iit", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def match_entities(all_rows: pd.DataFrame, threshold: float = 0.9) -> pd.DataFrame:
    """
    Adds `master_entity_id` and `match_score` columns by blocking on
    normalized institution name + state.
    """
    df = all_rows.copy()
    df["institution_name"] = df["institution_name"].fillna("")
    df["state"] = df["state"].fillna("")
    df["_norm_name"] = df["institution_name"].apply(_normalize_name)
    df["_block_key"] = df["_norm_name"] + "|" + df["state"].astype(str).str.lower()

    block_to_id = {key: f"INST_{i:04d}" for i, key in enumerate(sorted(df["_block_key"].unique()))}
    df["master_entity_id"] = df["_block_key"].map(block_to_id)
    df["match_score"] = 1.0  # exact block match in the MVP; Splink gives a real probability

    return df.drop(columns=["_norm_name", "_block_key"])

def extract_internship_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return internship rows when the source schema contains internship fields."""
    required = [
        "student_name", "company", "duration", "internship_year",
        "performance_remark", "institution_name",
        "source_database", "source_table", "source_record_id",
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        return pd.DataFrame(columns=required)
    return df.dropna(subset=["student_name", "company"])[required].copy()


def assign_internship_ids(internship_rows: pd.DataFrame) -> pd.DataFrame:
    """
    Generates a stable internship_id since no source system provides one.
    Blocks on student_name + company + internship_year — good enough for
    the MVP; a student with two internships at the same company in the
    same year would collide (accepted trade-off, revisit if it matters).
    """
    df = internship_rows.copy()
    if df.empty:
        return df.assign(internship_id=pd.Series(dtype="string"))
    df["_block_key"] = (
        df["student_name"].fillna("").astype(str).str.lower().str.strip() + "|" +
        df["company"].fillna("").astype(str).str.lower().str.strip() + "|" +
        df["internship_year"].fillna(0).astype(str)
    )

    block_to_id = {key: f"INTERN_{i:04d}" for i, key in enumerate(sorted(df["_block_key"].unique()))}
    df["internship_id"] = df["_block_key"].map(block_to_id)

    return df.drop(columns=["_block_key"])


def build_entity_mapping(resolved_df: pd.DataFrame) -> pd.DataFrame:
    """source_record -> master_entity_id lineage table (for ENTITY_MAPPING in Postgres)."""
    return resolved_df[[
        "master_entity_id", "institution_name", "source_system",
        "source_database", "source_record_id", "match_score",
    ]]


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01_INGESTION"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "03_SCHEMA_MAPPING"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "04_STANDARDIZATION"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "05_NORMALIZATION"))
    from INGESTION_ENGINE import ingest_all
    from SCHEMA_MAPPER import map_all
    from STANDARDIZER import standardize_all
    from NORMALIZER import normalize_all

    sample_dir = Path(__file__).resolve().parents[1] / "DATA" / "SAMPLE"
    normalized = normalize_all(standardize_all(map_all(ingest_all(sample_dir))))
    combined = pd.concat(normalized.values(), ignore_index=True)
    resolved = match_entities(combined)
    print(build_entity_mapping(resolved).to_string(index=False))
