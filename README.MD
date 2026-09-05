# E2E-KRS — fresh start, warehouse-centered architecture

This is a full rewrite. The earlier version (Postgres + Chroma as separate
stores, no dedup, no routing, no security layer) has been replaced with a
data-warehouse-centered design: every stage reads from and writes back to one
governed source of truth, instead of scattering state across tools.

## What this solves

- **Knowledge retrieval** — hybrid search (vector + BM25) → fusion → link
  expansion → rerank → generate → cite, all reading from the same warehouse.
- **Document overload** — hash + similarity dedup at ingestion, deterministic
  department/type routing, AND the proactive half: scheduled digests,
  compliance deadline surfacing, storage lifecycle review, analytics —
  nothing here waits to be asked, it's designed to push information out.

## Folder structure

```
E2E-KRS/
├── SOURCES/                    # input connectors — WhatsApp, email, SharePoint, folder watch
├── INGESTION_SERVICE/          # hash-dedup, triggers OCR/parse, writes to raw layer
├── WAREHOUSE/
│   ├── RAW/                    # processing logic for the raw layer
│   ├── STAGING/                # extraction, OCR, language detection logic
│   ├── INTERMEDIATE/           # classification, translation, similarity-dedup logic
│   └── MARTS/
│       ├── DOCUMENT_MART/      # promotion logic — intermediate → governed record
│       └── VECTOR_MART/        # chunking + embedding logic
├── STRUCTURED_INTEGRATION/     # AICTE-style arm — REAL working pipeline, not a stub (see its own README)
│   ├── AICTE_PIPELINE/         # 14-stage: ingest → discover → map → standardize → dedupe → embed → retrieve
│   └── AICTE_DB_MOCK/          # seeded MySQL/Postgres/Mongo simulation of fragmented source DBs
│   ├── NIFI_CONNECTORS/
│   ├── CDC_SERVICE/
│   └── ENTITY_RESOLUTION/
├── SECURITY_SERVICE/           # RBAC, sensitivity tiers, audit logging — gates BOTH serving paths
├── ROUTING_ENGINE/             # deterministic folder routing (rules, not LLM-controlled filesystem access)
├── RAG_SERVICE/                # document query endpoint: embed → hybrid search → rerank → generate → cite
├── FEDERATED_QUERY_SERVICE/    # merges RAG_SERVICE + structured search — the ONLY new query-side service
├── SCHEDULER/
│   ├── DIGEST_JOB/             # periodic "what arrived" summary
│   ├── COMPLIANCE_JOB/         # surfaces upcoming deadlines from compliance_flags
│   ├── LIFECYCLE_JOB/          # storage archival candidates
│   └── ANALYTICS_JOB/          # DuckDB-backed volume/trend queries
├── DATABASE/
│   ├── SCHEMA/                 # flat, numbered SQL — Postgres auto-init requires this, no subfolders
│   └── SEED/                   # sample/synthetic dev data
├── FRONTEND/                   # not started yet
├── .ENV.EXAMPLE
├── DOCKER-COMPOSE.YML
└── README.MD
```

## Two ingestion arms, one warehouse

`SOURCES`/`INGESTION_SERVICE`/`WAREHOUSE` handle unstructured documents.
`STRUCTURED_INTEGRATION` handles structured institutional databases
(AICTE-style). They stay deliberately separate — document dedup uses
embedding similarity, structured-record dedup uses fuzzy field matching
(Splink), and forcing one mechanism to do both degrades both. The only
connection point is `document_mart.institution_id`, a nullable foreign key
into `institution_mart` (see `008_STRUCTURED_MARTS.sql`) — a document can
optionally reference the structured record it's about, without either side
needing to know about the other's internals.

`FEDERATED_QUERY_SERVICE` is the one new piece that queries both and merges
results — everything below it stays exactly as specialized as before.



**Why `DATABASE/SCHEMA/` is flat despite the layered design**: Postgres's
docker-entrypoint-initdb.d only auto-runs `.sql` files directly inside the
mounted folder, not subdirectories. The layer numbering (001_RAW,
002_STAGING, 003_INTERMEDIATE, 004/005_MARTS, 006_SECURITY, 007_SCHEDULER)
preserves the build order even though the files sit side by side.

**Naming convention (unchanged from before)**: every folder and file
uppercase, except the `.py` extension itself, which must stay lowercase —
Python's import resolution is case-sensitive on Linux (where Docker
containers run) even though Windows isn't. `REQUIREMENTS.TXT`,
`DOCKERFILE`, `DOCKER-COMPOSE.YML` stay fully uppercase since they're
referenced by literal filename, not import path.

## Build order

1. **Freeze this schema** — review as a team before changing anything in `DATABASE/SCHEMA/`.
2. **Bring up infra**:
   ```
   docker compose -f DOCKER-COMPOSE.YML up postgres redis chroma minio
   ```
3. **Ingestion service** — hash-dedup + raw layer writes, before anything else.
4. **Warehouse staging/intermediate logic** — extraction, classification, similarity-dedup.
5. **Document mart + vector mart promotion logic**.
6. **Security layer** — before building any serving path, so nothing ships without it.
7. **Routing engine + RAG service** — both read from the same governed marts.
8. **Scheduler jobs** — the proactive overload-solving layer, last, once there's real data to summarize/flag.

## Security (standing requirement for this project)

No hardcoded credentials anywhere. `.env` never committed — only
`.ENV.EXAMPLE`. Every service reads secrets from environment variables.
Audit logging is not optional — every access to a `document_mart` record
goes through `audit_log`.
