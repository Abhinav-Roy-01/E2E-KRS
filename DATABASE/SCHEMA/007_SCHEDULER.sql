-- SCHEDULER SUPPORT: the proactive half of solving document overload — these
-- tables back the scheduled jobs (digest, compliance, lifecycle, analytics)
-- that push information out instead of waiting to be asked.

CREATE TABLE IF NOT EXISTS compliance_flags (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_mart_id  UUID NOT NULL REFERENCES document_mart(id) ON DELETE CASCADE,
    deadline          DATE,
    status            TEXT NOT NULL DEFAULT 'open',  -- 'open' | 'acknowledged' | 'resolved'
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT valid_compliance_status CHECK (
        status IN ('open','acknowledged','resolved')
    )
);

CREATE INDEX IF NOT EXISTS idx_compliance_flags_deadline ON compliance_flags(deadline);
CREATE INDEX IF NOT EXISTS idx_compliance_flags_status ON compliance_flags(status);

-- Record of each digest run, so the digest job doesn't re-summarize
-- documents already covered in a previous run.
CREATE TABLE IF NOT EXISTS digest_runs (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    period_start  TIMESTAMPTZ NOT NULL,
    period_end    TIMESTAMPTZ NOT NULL,
    document_count INT NOT NULL DEFAULT 0,
    delivered_to  TEXT,          -- email address / Slack channel / 'dashboard'
    run_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
