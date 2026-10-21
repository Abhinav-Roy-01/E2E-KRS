# UNTESTED CHANGES LOG

Code written while the dev machine was unavailable. Each entry says what was
verified (sandbox only: pure-Python logic) and what has NOT been run against
the real stack. Run the listed commands when the machine is back, then delete
the entry (or mark it verified) in the commit that confirms it.

## 1. STATE_BACKFILL (entity resolution second pass)

Files:
- STRUCTURED_INTEGRATION/AICTE_PIPELINE/06_DEDUPLICATION/STATE_BACKFILL.py  (new)
- STRUCTURED_INTEGRATION/AICTE_PIPELINE/12_TESTS/TEST_STATE_BACKFILL.py     (new)
- MAIN.py hook (manual 3-line edit, see below)

Verified in sandbox: unit tests pass; synthetic scale run (500 anchors + 700
noisy state-less groups) merged 691, left 9 ambiguous, 17s.
NOT verified: behaviour on the real seeded data; runtime there; DB_LOADER output.

MAIN.py hook -- directly after `resolved = match_entities(combined)` and
before `entity_map = build_entity_mapping(resolved)` add:

    from STATE_BACKFILL import backfill_stateless_entities
    resolved, backfill_report = backfill_stateless_entities(resolved)
    print(f"  state backfill: {backfill_report}")

Run when back:
    cd STRUCTURED_INTEGRATION\AICTE_PIPELINE
    .venv\Scripts\python.exe 12_TESTS\TEST_STATE_BACKFILL.py
    .venv\Scripts\python.exe MAIN.py
Expect: master entities drop from ~1220 toward ~500; check with
    docker exec -it aicte-canonical-postgres psql -U postgres -d aicte_canonical -c "SELECT COUNT(*), COUNT(*) FILTER (WHERE state = '') AS blank_state FROM institution;"
NOTE: institution is upserted (ON CONFLICT), so old stray rows from the
previous run stay in the table. For a clean count, truncate first:
    ... -c "TRUNCATE institution CASCADE;"
(also clears entity_mapping/data_lineage rows that reference it -- acceptable for the mock dataset only)
