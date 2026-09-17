# STRUCTURED_INTEGRATION

The AICTE-style arm -- reconciles institution/course/faculty/student/
internship records from multiple heterogeneous source databases.

**This is a real, working pipeline, not a stub** -- see `AICTE_PIPELINE/`.
14 stages: CONNECT -> INGEST -> DISCOVER -> MAP -> STANDARDIZE -> NORMALIZE
-> DEDUPLICATE -> CLASSIFY -> STORE -> EMBED -> INDEX -> RETRIEVE -> REASON
-> ANSWER. Full details in `AICTE_PIPELINE/14_DOCUMENTATION/ARCHITECTURE.MD`
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
docker compose -f DOCKER-COMPOSE.YML up postgres redis minio
docker compose -f STRUCTURED_INTEGRATION/AICTE_PIPELINE/DOCKER-COMPOSE.YML up
```

The connection between them is `document_mart.aicte_institution_id`
(see `DATABASE/SCHEMA/008_STRUCTURED_MARTS.SQL`) -- a plain identifier,
no cross-database foreign key (Postgres can't do that across instances).
`FEDERATED_QUERY_SERVICE` is what actually joins them, in application code.

## Resolved: local LLM everywhere, not a cloud API for either arm

`AICTE_PIPELINE/11_RETRIEVAL` previously called the Anthropic API for answer
synthesis. That was a real tension against this project's core pitch --
institutional/government data never leaves local infra -- since the
document side (`RAG_SERVICE`) already used local Ollama. Resolved: both
arms now synthesize answers via a local Qwen3:8B (Ollama), and both embed
via a local bge-m3 (Ollama) instead of AICTE's previous separate
sentence-transformers model. Two consequences worth knowing:
- Both arms' context vectors now live in the *same* embedding space, which
  is what makes a genuinely unified retrieval layer (rather than two
  separate RAG systems glued together) possible.
- `context_document.embedding` is `VECTOR(1024)` now, not `VECTOR(768)` --
  bge-m3's output size, not the old model's. Re-run `10_PGVECTOR`'s table
  creation on a fresh DB; this isn't a live migration of existing vectors.

## Why entity resolution stays separate from document dedup

Document dedup (`WAREHOUSE/INTERMEDIATE/`) uses embedding similarity.
`AICTE_PIPELINE/06_DEDUPLICATION/ENTITY_RESOLVER.py` uses Splink-based
fuzzy field matching. Different problems, kept as different code --
don't unify them into one generic "dedup service."
