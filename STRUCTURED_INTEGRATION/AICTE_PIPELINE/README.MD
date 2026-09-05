# SIH — AICTE DATA INTEGRATION & HARMONIZATION PLATFORM

A heterogeneous data harmonization and hybrid retrieval platform that converts
fragmented AICTE-style databases into a canonical, deduplicated, governed data
layer — structured facts in PostgreSQL, contextual knowledge as embeddings in
pgvector — so an LLM can answer natural-language questions with grounded,
sourced retrieval instead of guessing.

**Status: working MVP.** Ingestion through hybrid retrieval runs end-to-end
against sample data, with real entity resolution, real embeddings, and a
live pgvector-backed question-answering loop (mock LLM synthesis by default;
drops in a real Claude call the moment `ANTHROPIC_API_KEY` is set).

---

## Architecture

\`\`\`
CONNECT → INGEST → DISCOVER → MAP → STANDARDIZE → NORMALIZE → DEDUPLICATE
  → CLASSIFY → STORE (PostgreSQL) → EMBED → INDEX (pgvector) → RETRIEVE
  → REASON (LLM) → ANSWER
\`\`\`

### End-to-end flow

\`\`\`
                    SOURCE SYSTEMS
                (MySQL / Postgres / Mongo)
                          │
                          ▼
                 01  INGESTION
              (raw data + lineage stamp)
                          │
                          ▼
                 02  SCHEMA DISCOVERY
            (columns, dtypes, sample values)
                          │
                          ▼
                 03  SCHEMA MAPPING
        (source fields → canonical AICTE schema)
                          │
                          ▼
                 04  STANDARDIZATION
        (states, booleans, text — messy → clean)
                          │
                          ▼
                 05  NORMALIZATION
              (dtypes cast to canonical schema)
                          │
                          ▼
                 06  ENTITY RESOLUTION
      ("IIT Delhi" / "IIT-D" / "IIT, Delhi" → ONE id)
                          │
                          ▼
                 07  CONTEXT CLASSIFICATION
        (structured / relational / contextual)
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
       STRUCTURED +              CONTEXTUAL
       RELATIONAL                (remarks, feedback)
              │                       │
              ▼                       ▼
      08  POSTGRESQL          09  CONTEXT BUILDING
   (institution, course,      (raw field → rich sentence)
    faculty, student,                 │
    internship, lineage)              ▼
              │                09  EMBEDDING GENERATION
              │                (sentence-transformers, 768-dim)
              │                       │
              │                       ▼
              │                10  PGVECTOR
              │             (embedding + entity metadata)
              │                       │
              └───────────┬───────────┘
                          ▼
                 11  HYBRID RETRIEVAL
        (question → embed → search → rank → fuse)
                          │
                          ▼
                    LLM SYNTHESIS
      (answers ONLY from retrieved data — never invents facts)
                          │
                          ▼
                  GROUNDED ANSWER
               (traceable to source record)
\`\`\`

### Folder-by-folder

| Folder | Phase | What happens here |
|---|---|---|
| `01_INGESTION` | Ingest | Pull raw records from MySQL/Postgres/Mongo sample sources, stamp with lineage |
| `02_SCHEMA_DISCOVERY` | Discover | Inspect columns, types, sample values per source |
| `03_SCHEMA_MAPPING` | Map | Map source fields → canonical AICTE schema (see `MAPPING_RULES.yaml`) |
| `04_STANDARDIZATION` | Standardize | Normalize states, dates, booleans, text case |
| `05_NORMALIZATION` | Normalize | Cast dtypes into canonical shapes |
| `06_DEDUPLICATION` | Resolve | Fuzzy-match duplicate entities → master IDs (institutions + internships) |
| `07_CONTEXT_CLASSIFICATION` | Classify | Split fields into structured / relational / contextual |
| `08_POSTGRESQL` | Store | Load structured + relational data into Postgres, write lineage |
| `09_EMBEDDINGS` | Embed | Build rich context text, generate embeddings, push to pgvector |
| `10_PGVECTOR` | Index | Store embeddings + metadata; vector similarity search |
| `11_RETRIEVAL` | Retrieve | Hybrid retrieval: structured query + vector search + LLM synthesis |
| `12_TESTS` | Test | Pytest suite covering the deterministic pipeline stages |
| `13_CONFIG` | — | `CONFIG.yaml` (pipeline settings), `CANONICAL_SCHEMA.yaml` (field types) |
| `14_DOCUMENTATION` | — | `ARCHITECTURE.md` — design rationale, rules, known limitations |
| `DATA/SAMPLE` | — | Deliberately messy 3-source sample data (mirrors real AICTE inconsistency) |

A note on file naming: folders and script *stems* are CAPS
(`INGESTION_ENGINE`, `SCHEMA_DISCOVERY`, ...). Extensions stay lowercase
(`.py`, `.yaml`, `.sql`) because Python's import system only recognizes a
lowercase `.py` suffix.

---

## Setup

### 1. Python environment

\`\`\`powershell
python -m venv venv
venv\Scripts\activate
pip install python-dotenv pandas pyyaml psycopg[binary] pgvector sentence-transformers anthropic
\`\`\`

(`REQUIREMENTS/REQUIREMENTS.txt` has the full pinned list; `splink` and
`great-expectations` in there aren't wired into any code yet and can be
skipped if they fail to build on your Python version.)

### 2. Postgres + pgvector

Run a dedicated container (use a non-default port if you already run
Postgres elsewhere):

\`\`\`powershell
docker run -d --name aicte-postgres -e POSTGRES_PASSWORD=changeme -e POSTGRES_DB=aicte_canonical -p 5433:5432 pgvector/pgvector:pg16
\`\`\`

Enable the extension and load the schema:

\`\`\`powershell
docker exec -it aicte-postgres psql -U postgres -d aicte_canonical -c "CREATE EXTENSION vector;"
Get-Content 08_POSTGRESQL/DATABASE_SCHEMA.sql | docker exec -i aicte-postgres psql -U postgres -d aicte_canonical
\`\`\`

Create the pgvector context table (separate step — see note below on why
the index is *not* created automatically):

\`\`\`powershell
python -c "
from dotenv import load_dotenv
load_dotenv()
import sys
sys.path.insert(0, '10_PGVECTOR')
from VECTOR_STORE import CREATE_CONTEXT_TABLE_SQL, get_connection
conn = get_connection()
with conn.cursor() as cur:
    cur.execute(CREATE_CONTEXT_TABLE_SQL)
conn.commit()
print('context_document table ready')
"
\`\`\`

### 3. Configure `.env`

\`\`\`powershell
Copy-Item .ENV.EXAMPLE .env
notepad .env
\`\`\`

Set these to match your container:
\`\`\`
POSTGRES_HOST=localhost
POSTGRES_PORT=5433          # match whatever port you mapped above
POSTGRES_DB=aicte_canonical
POSTGRES_USER=postgres
POSTGRES_PASSWORD=changeme
\`\`\`

`ANTHROPIC_API_KEY` is optional — leave it blank or as the placeholder and
`11_RETRIEVAL` automatically falls back to a mock synthesizer that still
shows real retrieved context and rankings, just without an LLM-written
sentence on top.

---

## Running it

### Full deterministic pipeline (phases 01–07, sample data)

\`\`\`powershell
python MAIN.py
\`\`\`

Shows ingestion → schema discovery → mapping → standardization →
normalization → entity resolution (institutions + internships) → context
classification, all against the sample data in `DATA/SAMPLE/`.

### Push contextual data into pgvector

\`\`\`powershell
python 09_EMBEDDINGS/RUN_EMBEDDING_PIPELINE.py
\`\`\`

Builds rich context sentences from internship performance remarks, embeds
them, and writes them into the live `context_document` table.

### Ask a question (full retrieval loop)

\`\`\`powershell
python -c "
from dotenv import load_dotenv
load_dotenv()
import sys
sys.path.insert(0, '11_RETRIEVAL')
from HYBRID_RETRIEVER import answer_question
print(answer_question('How did Rahul Sharma perform in his internship?'))
"
\`\`\`

### Run tests

\`\`\`powershell
python -m pytest 12_TESTS/TEST_PIPELINE.py -v
\`\`\`

---

## Testing on your own data

The pipeline is source-count-agnostic — adding a new "system" means adding
a sample file + a few config lines, no code changes to the pipeline stages
themselves.

1. **Drop your file in `DATA/SAMPLE/`** — CSV or JSON, any column names.

2. **Register the source** in `13_CONFIG/CONFIG.yaml` under `sources:`:
   \`\`\`yaml
   sources:
     - name: your_source_db
       type: mysql   # or postgres / mongo — informational only in the MVP
       sample_file: DATA/SAMPLE/YOUR_FILE.csv
   \`\`\`

3. **Add its columns to `01_INGESTION/INGESTION_ENGINE.py`'s `ingest_all()`**
   — one more `load_from_sample(...)` call following the existing pattern.

4. **Map its fields to the canonical schema** in
   `03_SCHEMA_MAPPING/MAPPING_RULES.yaml`:
   \`\`\`yaml
   your_source_db:
     your_weird_column_name: institution_name
     your_state_field: state
   \`\`\`
   Any column *not* listed here passes through unmapped — check
   `02_SCHEMA_DISCOVERY/SCHEMA_DISCOVERY.py`'s output first to see what
   columns actually exist in your file before mapping them.

5. **If it introduces a genuinely new field type** (not institution/course/
   faculty/student/internship), add it to
   `13_CONFIG/CANONICAL_SCHEMA.yaml` with the right `type:`
   (`structured` / `relational` / `contextual`) — this is what
   `07_CONTEXT_CLASSIFICATION` uses to decide Postgres vs. pgvector.

6. **Re-run the pipeline**:
   \`\`\`powershell
   python MAIN.py
   \`\`\`
   Check the `06 ENTITY RESOLUTION` output — if your new source's institution
   names don't merge with existing ones, the issue is almost always a
   standardization gap (e.g. an unrecognized state abbreviation) — extend
   `STATE_ALIASES` in `04_STANDARDIZATION/STANDARDIZER.py`.

---

## Known issues / gotchas already fixed once (don't re-break these)

- **`docker ps` first.** Containers can silently exit (sleep, Docker Desktop
  restart). If something that worked before suddenly times out, check this
  before anything else.
- **`.env` must actually exist and be edited** — `Copy-Item .ENV.EXAMPLE .env`
  alone leaves you on the default port/password from the template.
- **Every standalone `python -c "..."` command needs its own
  `load_dotenv()`** — environment variables don't persist across separate
  process invocations.
- **Don't build the `ivfflat` index (`BUILD_VECTOR_INDEX_SQL` in
  `10_PGVECTOR/VECTOR_STORE.py`) on an empty or near-empty table.** It's an
  approximate index that gets permanently corrupted if built before data
  exists, and will silently return zero rows even after you insert real
  data later. Only call `build_vector_index()` once you have real volume
  (hundreds+ of rows); a full scan is instant below that.
- **Vector parameters need an explicit `::vector` cast** in raw SQL
  (`embedding <=> %s::vector`) — without it, Postgres may reject the query
  or (worse) silently misbehave depending on the psycopg/pgvector version
  combination.

See `14_DOCUMENTATION/ARCHITECTURE.md` for the full design rationale, the
three-types-of-information rule, and what's intentionally deferred
(Splink, NiFi, Kafka, Airflow — see that doc for how each one plugs in
later without a rewrite).