-- audit_log recorded WHO did WHAT-KIND-of-thing, but not WHAT they asked.
-- For query actions that is the part an auditor actually needs: the
-- question, which route answered it (rules / text_to_sql / vector_rag /
-- refused), and the exact SQL that ran. Answers are deliberately NOT stored.
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS detail TEXT;
