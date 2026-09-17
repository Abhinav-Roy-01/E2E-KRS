-- VECTOR MART: chunk text + embedding references, joined to document_mart on
-- document_mart_id. Dense vectors live in context_document below (pgvector,
-- not Chroma/Qdrant as originally planned -- see STRUCTURED_INTEGRATION/README.MD,
-- "Resolved: local LLM everywhere" -- this table is the structured half
-- (content, position, full-text index) that makes hybrid search possible.
CREATE TABLE IF NOT EXISTS vector_mart_chunks (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_mart_id  UUID NOT NULL REFERENCES document_mart(id) ON DELETE CASCADE,
    chunk_index       INT NOT NULL,
    content           TEXT NOT NULL,
    embedding_ref     TEXT,                 -- id in context_document (below)
    embedding_model   TEXT NOT NULL DEFAULT 'bge-m3',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_vector_mart_chunks_doc_id ON vector_mart_chunks(document_mart_id);

-- Full-text index for the BM25/sparse half of hybrid search.
ALTER TABLE vector_mart_chunks ADD COLUMN IF NOT EXISTS content_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED;
CREATE INDEX IF NOT EXISTS idx_vector_mart_chunks_tsv ON vector_mart_chunks USING GIN (content_tsv);

-- Dense vector half (pgvector). Same table shape and same embedding model
-- (bge-m3, local via Ollama) as AICTE_PIPELINE's own context_document table
-- -- deliberately, so both arms' vectors are directly comparable by one
-- unified retrieval layer instead of two separate RAG systems in two
-- separate vector spaces. See WAREHOUSE/MARTS/VECTOR_MART/APP/VECTOR_STORE.py.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS context_document (
    context_id          SERIAL PRIMARY KEY,
    entity_id            TEXT NOT NULL,
    entity_type          TEXT NOT NULL DEFAULT 'document',
    context_type         TEXT,
    context_text         TEXT NOT NULL,
    embedding            VECTOR(1024),  -- bge-m3 dimension
    source_database      TEXT,
    source_table         TEXT,
    source_record_id     TEXT,
    confidence           REAL DEFAULT 1.0,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    data_version         TEXT DEFAULT 'v1'
);

-- Do NOT build this index until the table has hundreds+ of rows -- an
-- ivfflat index on a near-empty table silently returns zero rows even
-- after real data is inserted later (see AICTE's VECTOR_STORE.py note).
-- CREATE INDEX IF NOT EXISTS idx_context_embedding
--     ON context_document USING ivfflat (embedding vector_cosine_ops);
