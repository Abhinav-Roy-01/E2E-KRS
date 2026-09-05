# STRUCTURED_INTEGRATION

The AICTE-style arm -- reconciles institution/course/faculty/student/
internship records from multiple heterogeneous source databases.

**This is a real, working pipeline, not a stub** -- see `AICTE_PIPELINE/`.
14 stages: CONNECT -> INGEST -> DISCOVER -> MAP -> STANDARDIZE -> NORMALIZE
-> DEDUPLICATE -> CLASSIFY -> STORE -> EMBED -> INDEX -> RETRIEVE -> REASON
-> ANSWER. Full details in `AICTE_PIPELINE/14_DOCUMENTATION/ARCHITECTURE.md`
and `AICTE_PIPELINE/README.MD`.

`AICTE_DB_MOCK/` is a seeded, multi-database (MySQL/Postgres/Mongo)
simulation of AICTE's real fragmented source systems -- lets the pipeline
be developed and demoed without live AICTE database access.

## Two separate Postgres instances -- by design, don't merge them

- This warehouse's Postgres: port `5432` (see root `DOCKER-COMPOSE.YML`)
- AICTE's canonical Postgres+pgvector: port `55432` (see
  `AICTE_PIPELINE/DOCKER-COMPOSE.YML`)

Bring both up independently:
```
docker compose -f DOCKER-COMPOSE.YML up postgres redis chroma minio
docker compose -f STRUCTURED_INTEGRATION/AICTE_PIPELINE/DOCKER-COMPOSE.YML up
```

The connection between them is `document_mart.aicte_institution_id`
(see `DATABASE/SCHEMA/008_STRUCTURED_MARTS.sql`) -- a plain identifier,
no cross-database foreign key (Postgres can't do that across instances).
`FEDERATED_QUERY_SERVICE` is what actually joins them, in application code.

## Open decision, not yet resolved -- flagging, not silently picking

`AICTE_PIPELINE/11_RETRIEVAL` uses the Anthropic API for answer synthesis
(with an honest mock-synthesis fallback when no API key is set). The
document side of E2E-KRS (`RAG_SERVICE`) uses local Ollama, specifically to
support the "nothing leaves the machine" data-sovereignty pitch. Using a
cloud LLM API for AICTE institutional data is a real tension against that
pitch -- worth a deliberate team decision (swap to local Ollama here too,
or accept the tradeoff and document why) rather than leaving it as-is by
default.

## Why entity resolution stays separate from document dedup

Document dedup (`WAREHOUSE/INTERMEDIATE/`) uses embedding similarity.
`AICTE_PIPELINE/06_DEDUPLICATION/ENTITY_RESOLVER.py` uses Splink-based
fuzzy field matching. Different problems, kept as different code --
don't unify them into one generic "dedup service."
