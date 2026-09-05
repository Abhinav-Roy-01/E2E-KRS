-- SECURITY LAYER: enforced between marts and every serving path (routing
-- engine AND rag query) — not per-consumer, so access rules can't be
-- accidentally bypassed by going through one path instead of the other.
CREATE TABLE IF NOT EXISTS users (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name         TEXT NOT NULL,
    email        TEXT UNIQUE NOT NULL,
    role         TEXT NOT NULL,     -- 'admin' | 'department_head' | 'employee'
    department   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Which departments/sensitivity tiers a role can see. Kept as data, not
-- hardcoded logic, so access rules can change without a code deploy.
CREATE TABLE IF NOT EXISTS department_access_rules (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role              TEXT NOT NULL,
    department        TEXT NOT NULL,
    max_sensitivity_tier TEXT NOT NULL DEFAULT 'internal',
    UNIQUE (role, department)
);

-- Every access to a document_mart record gets logged here — required for
-- any real government-facing audit trail.
CREATE TABLE IF NOT EXISTS audit_log (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          UUID REFERENCES users(id),
    document_mart_id UUID REFERENCES document_mart(id),
    action           TEXT NOT NULL,   -- 'view' | 'query' | 'download' | 'route' | 'archive'
    accessed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_doc ON audit_log(document_mart_id);
