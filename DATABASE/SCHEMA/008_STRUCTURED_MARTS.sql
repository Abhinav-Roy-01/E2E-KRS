-- CROSS-SYSTEM LINK, corrected after inspecting the actual AICTE pipeline.
--
-- The AICTE pipeline (STRUCTURED_INTEGRATION/AICTE_PIPELINE) runs its OWN
-- Postgres+pgvector container (aicte-canonical-postgres, port 55432) with
-- its own schema -- see AICTE_PIPELINE/08_POSTGRESQL/DATABASE_SCHEMA.sql for
-- the real institution/course/faculty/student/internship tables, already
-- built and tested. This file does NOT duplicate that schema here.
--
-- Because these are two separate Postgres instances (this warehouse on
-- 5432, AICTE's canonical DB on 55432), a real SQL foreign key cannot span
-- them. The link is a plain, unenforced identifier -- the actual join
-- happens in application code, in FEDERATED_QUERY_SERVICE, which queries
-- both databases and merges results. This is the correct way to merge two
-- already-working systems without breaking either.

ALTER TABLE document_mart ADD COLUMN IF NOT EXISTS aicte_institution_id TEXT;
CREATE INDEX IF NOT EXISTS idx_document_mart_aicte_institution ON document_mart(aicte_institution_id);

-- No FK constraint here on purpose -- see comment above.
