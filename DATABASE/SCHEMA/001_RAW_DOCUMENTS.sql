CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- RAW LAYER: exactly what arrived, untouched, from any source.
CREATE TABLE IF NOT EXISTS raw_documents (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source            TEXT NOT NULL,        -- 'whatsapp' | 'email' | 'sharepoint' | 'folder_watch' | 'manual_upload'
    source_message_id TEXT,                 -- e.g. WhatsApp media_id, email message-id — for traceability back to origin
    original_filename TEXT NOT NULL,
    storage_key       TEXT NOT NULL,        -- MinIO object key, e.g. raw/<id>
    sha256_hash       TEXT NOT NULL,        -- exact-duplicate detection, computed before anything else runs
    filetype          TEXT NOT NULL,
    received_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_status        TEXT NOT NULL DEFAULT 'received',
        -- 'received' | 'staged' | 'duplicate_exact' | 'failed'
    CONSTRAINT valid_raw_status CHECK (
        raw_status IN ('received','staged','duplicate_exact','failed')
    )
);

CREATE INDEX IF NOT EXISTS idx_raw_documents_hash ON raw_documents(sha256_hash);
CREATE INDEX IF NOT EXISTS idx_raw_documents_status ON raw_documents(raw_status);
CREATE INDEX IF NOT EXISTS idx_raw_documents_source ON raw_documents(source);
