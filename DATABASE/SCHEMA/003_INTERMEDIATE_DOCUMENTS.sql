-- INTERMEDIATE LAYER: classification, translation, and the similarity-based
-- duplicate/related check — the business logic layer, before anything is
-- promoted to a governed mart record.
CREATE TABLE IF NOT EXISTS intermediate_documents (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    staging_document_id  UUID NOT NULL REFERENCES staging_documents(id) ON DELETE CASCADE,
    department            TEXT,
    doc_type              TEXT,
    domain                TEXT,             -- finer-grained than department, e.g. 'railway_signalling'
    project                TEXT,
    classification_confidence FLOAT,        -- gates auto-route vs human review (see routing engine)
    translated_text        TEXT,             -- NULL if source language is already English
    translation_confidence FLOAT,
    similarity_verdict     TEXT,             -- 'duplicate' | 'related' | 'no_match' | NULL (not yet checked)
    duplicate_of_document_id UUID,           -- points to an existing document_mart.id if verdict = 'duplicate'
    intermediate_status    TEXT NOT NULL DEFAULT 'pending',
        -- 'pending' | 'classified' | 'chunked' | 'promoted' | 'needs_review' | 'failed'
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT valid_similarity_verdict CHECK (
        similarity_verdict IS NULL OR similarity_verdict IN ('duplicate','related','no_match')
    ),
    CONSTRAINT valid_intermediate_status CHECK (
        intermediate_status IN ('pending','classified','chunked','promoted','needs_review','failed')
    )
);

CREATE INDEX IF NOT EXISTS idx_intermediate_documents_staging_id ON intermediate_documents(staging_document_id);
CREATE INDEX IF NOT EXISTS idx_intermediate_documents_status ON intermediate_documents(intermediate_status);
CREATE INDEX IF NOT EXISTS idx_intermediate_documents_department ON intermediate_documents(department);
