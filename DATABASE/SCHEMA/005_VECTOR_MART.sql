-- VECTOR MART: chunk text + embedding references, joined to document_mart on
-- document_mart_id. Actual vectors live in Chroma/Qdrant — this table is the
-- structured half (content, position, full-text index) that makes hybrid
-- search possible.
CREATE TABLE IF NOT EXISTS vector_mart_chunks (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_mart_id  UUID NOT NULL REFERENCES document_mart(id) ON DELETE CASCADE,
    chunk_index       INT NOT NULL,
    content           TEXT NOT NULL,
    embedding_ref     TEXT,                 -- id in Chroma/Qdrant
    embedding_model   TEXT NOT NULL DEFAULT 'nomic-embed-text',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_vector_mart_chunks_doc_id ON vector_mart_chunks(document_mart_id);

-- Full-text index for the BM25/sparse half of hybrid search.
ALTER TABLE vector_mart_chunks ADD COLUMN IF NOT EXISTS content_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED;
CREATE INDEX IF NOT EXISTS idx_vector_mart_chunks_tsv ON vector_mart_chunks USING GIN (content_tsv);
