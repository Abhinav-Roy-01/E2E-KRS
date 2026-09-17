-- CANONICAL STRUCTURED + RELATIONAL LAYER
-- Run this against POSTGRES_DB from .env before DB_LOADER.py

CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector lives inside this same DB (see 10_PGVECTOR)

CREATE TABLE IF NOT EXISTS institution (
    institution_id      TEXT PRIMARY KEY,
    institution_name    TEXT NOT NULL,
    state                TEXT,
    approval_status     BOOLEAN,
    nirf_rank            INTEGER,
    naac_grade           TEXT
);

CREATE TABLE IF NOT EXISTS course (
    course_id            TEXT PRIMARY KEY,
    institution_id       TEXT REFERENCES institution(institution_id),
    course_name          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS faculty (
    faculty_id            TEXT PRIMARY KEY,
    institution_id        TEXT REFERENCES institution(institution_id),
    faculty_name           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS student (
    student_id             TEXT PRIMARY KEY,
    institution_id         TEXT REFERENCES institution(institution_id),
    student_name           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS internship (
    internship_id          TEXT PRIMARY KEY,
    student_id              TEXT REFERENCES student(student_id),
    company                  TEXT,
    duration                 TEXT,
    internship_year         INTEGER
);

-- Lineage: every canonical record traces back to its source(s).
CREATE TABLE IF NOT EXISTS entity_mapping (
    id                       SERIAL PRIMARY KEY,
    master_entity_id         TEXT NOT NULL,
    entity_type               TEXT NOT NULL,
    source_system              TEXT NOT NULL,
    source_database            TEXT NOT NULL,
    source_table                TEXT,
    source_record_id           TEXT NOT NULL,
    match_score                 REAL,
    created_at                  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS data_lineage (
    id                        SERIAL PRIMARY KEY,
    canonical_entity_id        TEXT NOT NULL,
    source_system                TEXT NOT NULL,
    source_database              TEXT NOT NULL,
    source_table                  TEXT,
    source_record_id             TEXT,
    transformation_version        TEXT DEFAULT 'v1',
    validation_status              TEXT DEFAULT 'pending',
    ingestion_timestamp             TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_entity_mapping_master ON entity_mapping(master_entity_id);
CREATE INDEX IF NOT EXISTS idx_institution_state ON institution(state);
