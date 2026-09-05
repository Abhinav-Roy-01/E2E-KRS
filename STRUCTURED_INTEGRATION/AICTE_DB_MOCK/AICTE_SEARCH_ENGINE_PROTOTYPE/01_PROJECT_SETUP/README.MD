# AICTE Search Engine Prototype — 5 Fragmented Mock Data Sources

A hackathon prototype that simulates how a body like AICTE ends up with
**disconnected databases** across colleges, courses, faculty, scholarships and
approvals — each built by a different vendor/team, on a different technology,
with **no shared master ID** and **deliberately inconsistent naming**.

This step only scaffolds + seeds the 5 fragmented sources. The ETL /
normalization layer, search index and API are **not** built yet (next steps).

---

## What the 5 sources represent

| # | Source | Technology | Container / Port | What it represents | Why this technology |
|---|--------|-----------|------------------|--------------------|---------------------|
| 1 | Colleges / Institutes | **MySQL 8** | `aicte-mysql` · host `3307` | The institutes master list (AICTE codes, approval status) | The "official" relational system, well-structured but with copy-paste errors |
| 2 | Courses | **PostgreSQL 16** | `aicte-postgres` · host `5433` (db `courses_db`) | Courses offered per college, `college_name` is free text, **not a FK** | A second team's normalized relational DB with no reference to source 1 |
| 3 | Faculty | **PostgreSQL 16** | same instance, db `faculty_db` | Faculty records referencing institutes by free text | Separate DB on the same server — different schema, same fragmentation |
| 4 | Scholarships & Schemes | **MongoDB 7** | `aicte-mongo` · host `27017` (db `aicte_scholarships`) | Schema-flexible scheme documents | Schemaless docs with genuinely varied field sets (no uniform keys) |
| 5 | Approvals / Legacy | **Flat CSV files** | no server — `data/legacy/*.csv` | Old spreadsheet exports nobody maintains | Not all fragmented data is database-shaped; some is just exported files |

Host ports were remapped because local services already occupy 3306 (MySQL)
and 5432 (PostgreSQL): MySQL → `3307`, PostgreSQL → `5433`, MongoDB → `27017`.

## Directory layout

```
├── docker-compose.yml            # MySQL + PostgreSQL + MongoDB + Adminer
├── .env / .env.example           # all credentials (nothing hardcoded)
├── requirements.txt              # faker, pandas, pymysql, psycopg, pymongo, python-dotenv
├── seed_all.py                   # orchestrator: seeds all 5 sources + prints summary
├── institute_registry.json       # canonical 150 institutes (internal, seeding-only)
├── conflicts_seeded.json         # GROUND TRUTH: every planted issue, machine-readable
├── seed/
│   ├── generate_registry.py      # builds institute_registry.json deterministically
│   ├── name_noise_utils.py       # the inconsistency generator (reused everywhere)
│   ├── conflicts_log.py          # appends planted issues to conflicts_seeded.json
│   ├── db_utils.py               # .env loading + wait-for-service retry loops
│   ├── mysql_seed.py             # source 1
│   ├── postgres_courses_seed.py  # source 2
│   ├── postgres_faculty_seed.py  # source 3
│   ├── mongo_seed.py             # source 4
│   └── generate_legacy_csv.py    # source 5 (pandas -> disk, no DB)
├── data/legacy/
│   ├── nba_autonomous_status.csv # date format DD-MM-YYYY, has a stray empty column
│   ├── closed_institutes.csv     # date format YYYY/MM/DD
│   └── unapproved_list.csv       # date format DD Mon YYYY
└── docker/postgres-init/         # creates faculty_db on first boot
```

## How to run

```bash
# 1. Start databases (first run pulls images)
docker compose up -d --wait

# 2. Seed everything (venv: internalenv/Scripts/python.exe)
internalenv/Scripts/python.exe seed_all.py
```

`seed_all.py` prints a per-source summary plus a final table: row counts,
distinct names, approximate registry overlap, and how many issues were
planted. Re-running is **idempotent**: every script drops/truncates its
table/collection first and the registry + conflict log are regenerated fresh.

## One-command control script: `manage.sh`

All of the above (and more) is wrapped in a single script — run it from Git
Bash (`manage.bat` also works for double-clicking on Windows):

```bash
bash manage.sh setup     # start containers + seed everything (the full setup)
bash manage.sh seed      # re-seed all 5 sources (idempotent)
bash manage.sh counts    # row counts for all 5 sources + planted-issue counts
bash manage.sh samples   # peek at sample rows from each source
bash manage.sh status    # container health
bash manage.sh mysql     # interactive MySQL shell  (also: courses, faculty, mongo)
bash manage.sh adminer   # open the web UI at http://localhost:8080
bash manage.sh stop      # stop containers (data kept)
bash manage.sh wipe      # delete containers + all data  (asks for confirmation)
bash manage.sh help      # full command list
```

---

## Deliberate inconsistencies & conflicts planted (show this to judges)

### Cross-source conflicts (14) — same institute, contradicting facts

| # | Type | Example institute | MySQL says | Another source says |
|---|------|-------------------|------------|---------------------|
| 5 | Approved but closed | Lendi College of Engineering and Technology, Hubballi | `Approved` | `closed_institutes.csv` (closure year) |
| 3 | Approved but unapproved-listed | SRM Institute of Engineering and Technology, Kolkata | `Approved` | `unapproved_list.csv` (flagged) |
| 2 | Rejected but still offers courses | Kalasalingam College of Engineering and Technology, Karimnagar | `Rejected` | 3 courses in `courses_db` |
| 2 | Rejected but still has a scholarship | Amrita College of Engineering, Nizamabad | `Rejected` | scholarship doc lists it in `applicable_institutes` |
| 2 | Under review but NBA-accredited | Raghu Institute of Technology, Bikaner | `Under Review` | `nba_autonomous_status.csv` = `Accredited` |

### Within-source duplicates (27)

| Source | Count | Pattern |
|--------|-------|---------|
| MySQL `institutes` | 9 | same `AICTE_Code` reused w/ different spelling · copy-paste row (only `Last_Updated` differs) · exact dup |
| PostgreSQL `courses` | 12 | 6 exact dups + 6 near-dups (fee ±10%, `last_synced` drift) |
| MongoDB `scholarships` | 6 | 3 exact + 3 near-dup documents (same `scheme_name`) |

### Orphaned / legacy-only records (16)

- 7 faculty rows referencing institutes that exist **nowhere** (`faculty_db`)
- 3 course rows for non-existent colleges (`courses_db`)
- 6 institutes that appear **only** in the legacy CSVs

### Name inconsistency (the core mechanic)

`seed/name_noise_utils.py` takes a canonical name and produces noisy variants
(abbreviations like `Inst.`/`Engg.`, `&` ↔ `and`, dropped `Shri`, ALL CAPS,
city reordering, trailing punctuation, extra whitespace). Applied per source:
MySQL ~15% of rows, Postgres ~20% of references, Mongo ~30% of refs, CSVs the
messiest (~50% + stray whitespace). So **the same institute is spelled
differently in every database** — e.g. `Shri Venkateswara College of
Engineering, Guntur` may appear as `Inst. of Tech.` variants elsewhere.

### Timestamp drift (for conflict-detection demos)

- MySQL: recent (last 90 days)
- MongoDB: recent (last 60 days)
- PostgreSQL: mixed (40% 1.5–5 years old, 60% recent)
- CSVs: stale (2023–2024, i.e. 2–3 years old), 3 different date formats

Full ground truth is in **`conflicts_seeded.json`** (`cross_source_conflicts`,
`within_source_duplicates`, `orphaned_records`) — use it to prove your
ETL/dedup layer catches exactly what was planted.

---

## Managing the databases

Everything runs in Docker. All credentials are in `.env`.

### Quick management UI — Adminer

`http://localhost:8080` — browser UI for **MySQL** and **PostgreSQL**:
- MySQL: server `mysql` (container name), user `aicte_app`, password `aicte_pass`, db `aicte_institutes`
- PostgreSQL: server `postgres`, user `postgres`, password `postgres`, db `courses_db` or `faculty_db`
- (MongoDB is not supported by Adminer — use `mongosh`, below)

### MySQL (institutes) — port 3307

```bash
docker exec -it aicte-mysql mysql -uaicte_app -paicte_pass aicte_institutes -e "SELECT COUNT(*) FROM institutes;"
docker exec -it aicte-mysql mysql -uaicte_app -paicte_pass aicte_institutes -e "SELECT Institute_Name, Approval_Status FROM institutes LIMIT 10;"
```

### PostgreSQL (courses_db, faculty_db) — port 5433

> **Note:** the postgres image is built from `docker/postgres/Dockerfile`, which
> restores the legacy `Asia/Calcutta` timezone alias that the stock
> `postgres:16` image omits. DBeaver on Windows sends this name as the
> `TimeZone` connection parameter and the stock image rejects it with
> `FATAL: invalid value for parameter "TimeZone": "Asia/Calcutta"`. If you
> prefer, you can instead set the connection's `TimeZone` driver property to
> `Asia/Kolkata` in DBeaver.

```bash
docker exec -it aicte-postgres psql -Upostgres -d courses_db -c "SELECT COUNT(*) FROM courses;"
docker exec -it aicte-postgres psql -Upostgres -d faculty_db -c "SELECT designation, COUNT(*) FROM faculty GROUP BY designation;"
```

### MongoDB (scholarships) — port 27017

```bash
docker exec -it aicte-mongo mongosh aicte_scholarships --eval "db.scholarships.countDocuments()"
docker exec -it aicte-mongo mongosh aicte_scholarships --eval "db.scholarships.findOne()"
```

### Legacy CSVs

Plain files in `data/legacy/` — open in Excel or any editor. They are **not**
loaded into any database on purpose (that's the "legacy export" point).

### GUI tools (recommended for demos)

- **DBeaver** (free) — connect to all 3: MySQL `localhost:3307`, PostgreSQL
  `localhost:5433`, MongoDB `localhost:27017`
- **TablePlus / DataGrip** — same endpoints
- **MongoDB Compass** — `mongodb://localhost:27017/aicte_scholarships`

### Common operations

```bash
docker compose ps                 # see health of all containers
docker compose logs mysql         # container logs
docker compose down               # stop containers (data persists in volumes)
docker compose down -v            # stop + DELETE all seeded data (fresh start)
internalenv/Scripts/python.exe seed_all.py   # re-seed any time (idempotent)
```

---

## Not built yet (next steps)

The ETL/normalization layer, the search index (Elasticsearch/Meilisearch) and
the FastAPI unified-search API. `conflicts_seeded.json` is ready to be the
ground truth for validating the dedup layer.
