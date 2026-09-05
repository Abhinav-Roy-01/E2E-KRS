"""
01_INGESTION — pull raw records from every source system and stamp them
with lineage metadata before anything is transformed.

The default is sample-data mode for deterministic smoke tests, but the live mode
reads from the real AICTE_DB sources when `USE_SAMPLE_DATA=false` in `.env`.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from sqlalchemy import create_engine
except ImportError:  # pragma: no cover
    create_engine = None

RAW_METADATA_FIELDS = [
    "source_system", "source_database", "source_table",
    "source_record_id", "ingestion_timestamp",
]


def _stamp(df: pd.DataFrame, source_system: str, source_database: str, source_table: str) -> pd.DataFrame:
    df = df.copy()
    df["source_system"] = source_system
    df["source_database"] = source_database
    df["source_table"] = source_table
    df["source_record_id"] = df.index.astype(str)
    df["ingestion_timestamp"] = datetime.now(timezone.utc).isoformat()
    return df


def load_from_sample(path: Path, source_system: str, source_database: str, source_table: str) -> pd.DataFrame:
    if path.suffix == ".csv":
        df = pd.read_csv(path)
    elif path.suffix == ".json":
        df = pd.json_normalize(json.loads(path.read_text()))
    else:
        raise ValueError(f"Unsupported sample format: {path.suffix}")
    return _stamp(df, source_system, source_database, source_table)


def _mysql_live_dataframe(uri: str, table_name: str, source_system: str, source_database: str) -> pd.DataFrame:
    if create_engine is None:
        raise RuntimeError("SQLAlchemy is required for live ingestion")
    engine = create_engine(uri)
    df = pd.read_sql_query(f"SELECT * FROM `{table_name}`", engine)
    return _stamp(df, source_system, source_database, table_name)


def _postgres_live_dataframe(uri: str, table_name: str, source_system: str, source_database: str) -> pd.DataFrame:
    if create_engine is None:
        raise RuntimeError("SQLAlchemy is required for live ingestion")
    engine = create_engine(uri)
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", engine)
    return _stamp(df, source_system, source_database, table_name)


def _mongo_live_dataframe(uri: str, database_name: str, collection_name: str, source_system: str, source_database: str) -> pd.DataFrame:
    try:
        from pymongo import MongoClient
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pymongo is required for live Mongo ingestion") from exc

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        docs = list(client[database_name][collection_name].find({}))
    finally:
        client.close()

    if not docs:
        return pd.DataFrame(columns=["_id"]).pipe(lambda df: _stamp(df, source_system, source_database, collection_name))
    df = pd.json_normalize(docs)
    return _stamp(df, source_system, source_database, collection_name)


def _live_sources() -> dict[str, pd.DataFrame]:
    mysql_uri = os.getenv("SOURCE_MYSQL_URI")
    courses_uri = os.getenv("SOURCE_POSTGRES_COURSES_URI")
    faculty_uri = os.getenv("SOURCE_POSTGRES_FACULTY_URI")
    mongo_uri = os.getenv("SOURCE_MONGO_URI", "mongodb://localhost:27017")
    mongo_db = os.getenv("SOURCE_MONGO_DB", "aicte_scholarships")
    mongo_collection = os.getenv("SOURCE_MONGO_COLLECTION", "scholarships")

    return {
        "institutes": _mysql_live_dataframe(mysql_uri, "institutes", "mysql", "aicte_institutes"),
        "courses": _postgres_live_dataframe(courses_uri, "courses", "postgres", "courses_db"),
        "faculty": _postgres_live_dataframe(faculty_uri, "faculty", "postgres", "faculty_db"),
        "scholarships": _mongo_live_dataframe(mongo_uri, mongo_db, mongo_collection, "mongo", mongo_db),
    }


def _sample_sources(sample_dir: Path | None) -> dict[str, pd.DataFrame]:
    if sample_dir is None:
        raise ValueError("A sample_dir is required when USE_SAMPLE_DATA=true")
    return {
        "institution_db": load_from_sample(
            sample_dir / "SOURCE_A_INSTITUTION.csv", "mysql", "institution_db", "institution"
        ),
        "course_db": load_from_sample(
            sample_dir / "SOURCE_B_INSTITUTION.csv", "postgres", "course_db", "institution"
        ),
        "faculty_db": load_from_sample(
            sample_dir / "SOURCE_C_INSTITUTION.json", "mongo", "faculty_db", "institution"
        ),
    }


def ingest_all(sample_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """Returns {source_name: raw_dataframe_with_lineage}."""
    use_sample_data = str(os.getenv("USE_SAMPLE_DATA", "true")).strip().lower() == "true"
    if sample_dir is not None or use_sample_data:
        return _sample_sources(sample_dir)
    return _live_sources()


if __name__ == "__main__":
    sample_dir = Path(__file__).resolve().parents[1] / "DATA" / "SAMPLE"
    raw = ingest_all(sample_dir if str(os.getenv("USE_SAMPLE_DATA", "true")).strip().lower() == "true" else None)
    for name, df in raw.items():
        print(f"\n=== {name} ({len(df)} rows) ===")
        print(df.head())
