-- STAGING LAYER: parsed/extracted text, cleaned, language-detected.
-- Nothing about department, doc_type, or business meaning lives here yet.
CREATE TABLE IF NOT EXISTS staging_documents (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    raw_document_id   UUID NOT NULL REFERENCES raw_documents(id) ON DELETE CASCADE,
    extracted_text    TEXT,
    ocr_used          BOOLEAN NOT NULL DEFAULT FALSE,
    vision_llm_used   BOOLEAN NOT NULL DEFAULT FALSE,  -- true if OCR failed and vision-LLM fallback ran
    language          TEXT,                             -- ISO 639-1-ish code, set here not in raw
    staged_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    staging_status    TEXT NOT NULL DEFAULT 'staged',
        -- 'staged' | 'classified' | 'failed'
    CONSTRAINT valid_staging_status CHECK (
        staging_status IN ('staged','classified','failed')
    )
);

CREATE INDEX IF NOT EXISTS idx_staging_documents_raw_id ON staging_documents(raw_document_id);
CREATE INDEX IF NOT EXISTS idx_staging_documents_status ON staging_documents(staging_status);
