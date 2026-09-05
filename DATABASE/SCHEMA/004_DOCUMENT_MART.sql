-- DOCUMENT MART: the single governed record every downstream consumer reads
-- from (routing engine, RAG query, scheduler jobs, security layer). This is
-- the "source of truth" table — logical identity lives here even if physical
-- storage location changes later.
CREATE TABLE IF NOT EXISTS document_mart (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    intermediate_document_id UUID NOT NULL REFERENCES intermediate_documents(id) ON DELETE CASCADE,
    original_filename        TEXT NOT NULL,
    department               TEXT NOT NULL,
    doc_type                 TEXT NOT NULL,
    domain                   TEXT,
    project                  TEXT,
    language                 TEXT,
    sensitivity_tier         TEXT NOT NULL DEFAULT 'internal',
        -- 'public' | 'internal' | 'restricted' | 'confidential' — enforced by security layer
    storage_path              TEXT,          -- physical location, e.g. Engineering/Railway Signalling/Circuit Diagrams/...
    storage_key                TEXT NOT NULL, -- MinIO key of the FINAL routed copy
    last_accessed_at           TIMESTAMPTZ,   -- drives storage lifecycle / archival decisions
    mart_status                 TEXT NOT NULL DEFAULT 'active',
        -- 'active' | 'archived' | 'flagged_duplicate'
    promoted_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT valid_sensitivity_tier CHECK (
        sensitivity_tier IN ('public','internal','restricted','confidential')
    ),
    CONSTRAINT valid_mart_status CHECK (
        mart_status IN ('active','archived','flagged_duplicate')
    )
);

CREATE INDEX IF NOT EXISTS idx_document_mart_department ON document_mart(department);
CREATE INDEX IF NOT EXISTS idx_document_mart_doc_type ON document_mart(doc_type);
CREATE INDEX IF NOT EXISTS idx_document_mart_sensitivity ON document_mart(sensitivity_tier);
CREATE INDEX IF NOT EXISTS idx_document_mart_last_accessed ON document_mart(last_accessed_at);

-- Related-document links, populated by the similarity check (not duplicates —
-- those get flagged via intermediate_documents.duplicate_of_document_id instead).
CREATE TABLE IF NOT EXISTS document_links (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_doc_id    UUID NOT NULL REFERENCES document_mart(id) ON DELETE CASCADE,
    related_doc_id   UUID NOT NULL REFERENCES document_mart(id) ON DELETE CASCADE,
    similarity_score FLOAT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_doc_id, related_doc_id)
);
