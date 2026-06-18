# PITWALL·AI

**An AI-powered Formula 1 race intelligence platform** — combining real-time telemetry ingestion, a multi-agent AI reasoning layer (LangGraph), retrieval-augmented generation over historical race data, and an interactive React dashboard.

This README is written as a complete project brief for an AI coding agent (e.g. Antigravity) to understand the project's purpose, architecture, current state, conventions, and roadmap, and to continue development consistently with what has already been built.

---

## 1. Project vision

PITWALL·AI aims to be a "race engineer's assistant" — a system that ingests live and historical Formula 1 data, reasons about strategy and performance like a human race engineer, and answers natural-language questions about races, drivers, and strategy decisions ("Has a safety car at Monza ever changed a championship result?", "Why is Leclerc losing time compared to lap 18?", "What's the optimal pit window for Verstappen right now?").

It is built as a flagship portfolio project demonstrating:
- Full-stack AI engineering (FastAPI + React + async Postgres/pgvector + Redis)
- Multi-agent orchestration with LangGraph
- RAG over a domain-specific knowledge base
- Real-world data pipeline engineering with a public, free API (OpenF1)

---

## 2. Tech stack

### Backend
- **FastAPI** — REST API + WebSocket layer
- **SQLAlchemy 2.0 (async)** — ORM, using `asyncpg` driver
- **PostgreSQL 16 + pgvector** — primary datastore and vector store for embeddings
- **Redis** — caching layer for live session state
- **Alembic** — database migrations (to be introduced in Phase 2)
- **LangGraph + LangChain** — multi-agent orchestration (Phase 3+)
- **OpenAI API** — LLM backend for agents (Phase 3+, key currently unset)
- **sentence-transformers** — embeddings for RAG (`all-MiniLM-L6-v2`, 384-dim)

### Data sources
- **OpenF1 API** (`https://api.openf1.org/v1`) — primary data source. Free, no API key required. Provides meetings, sessions, drivers, laps, pit stops, car telemetry, position data, intervals, and race control messages.
- (Planned) Ergast API and FastF1 for historical results and richer lap/tyre data.

### Frontend (Phase 5, not yet started)
- **React** (Vite) — dashboard with three panels: live telemetry, strategy panel, and an AI intelligence chat interface.

### Infrastructure
- **Docker Compose** — runs PostgreSQL (`pgvector/pgvector:pg16`) and Redis locally.

---

## 3. Environment

- **OS**: Windows 11, PowerShell
- **Python**: 3.13
- **Virtual environment**: `D:\Projects\pitwall-ai\backend\venv`
  - Activate: `venv\Scripts\activate`
  - Or call directly: `venv\Scripts\python.exe -m <command>`
- **Project root**: `D:\Projects\pitwall-ai`

### Running the project

```powershell
# 1. Start infrastructure (Postgres + Redis) from project root
cd D:\Projects\pitwall-ai
docker compose up -d
docker compose ps   # confirm both containers are "healthy"

# 2. Start the backend API
cd backend
venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- API root: `http://127.0.0.1:8000/`
- Health check: `http://127.0.0.1:8000/health`
- On successful startup with Docker running, you should see:
  ```
  🚀 PITWALL·AI starting up...
  ✅ Database initialised — all tables created
  INFO:     Application startup complete.
  ```
- If Docker/Postgres is not running, the app still starts (graceful degradation) but prints:
  ```
  ⚠️  Database not available yet: ...
     Start Docker and run again to initialise tables.
  ```

### Quick data check (no DB required)

```powershell
cd backend
venv\Scripts\python.exe ingestion\openf1.py          # prints latest meeting + session
venv\Scripts\python.exe ingestion\openf1.py 9158      # ingests/prints data for a specific session_key
```

---

## 4. Project structure

```
pitwall-ai/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entry point, lifespan, CORS, /health
│   │   ├── config.py            # Pydantic settings, loads .env
│   │   ├── database.py          # Async SQLAlchemy engine, session factory, init_db()
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── f1_models.py     # SQLAlchemy ORM models (see section 6)
│   │   ├── api/
│   │   │   └── __init__.py      # (Phase 2) REST route modules go here
│   │   └── agents/
│   │       └── __init__.py      # (Phase 3) LangGraph agent nodes go here
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── openf1.py            # Async OpenF1 API client + CLI ingestion script
│   ├── requirements.txt
│   ├── .env                     # local environment variables (not committed)
│   └── venv/                    # Python virtual environment (not committed)
├── frontend/                     # React app (Phase 5, currently empty)
├── docker-compose.yml            # Postgres (pgvector) + Redis
└── README.md                     # this file
```

---

## 5. Configuration (`backend/.env`)

```env
# Database
DATABASE_URL=postgresql+asyncpg://pitwall:pitwall_secret@localhost:5432/pitwall_db

# Redis
REDIS_URL=redis://localhost:6379

# OpenAI (required from Phase 3 onward)
OPENAI_API_KEY=

# App
APP_ENV=development
APP_DEBUG=True
SECRET_KEY=pitwall_dev_secret_change_in_prod
```

Loaded via `app/config.py` (`pydantic-settings`). `get_settings()` is cached with `@lru_cache`.

### `docker-compose.yml` summary
- `postgres`: image `pgvector/pgvector:pg16`, db `pitwall_db`, user `pitwall` / pass `pitwall_secret`, port `5432`, healthcheck via `pg_isready`.
- `redis`: image `redis:7-alpine`, port `6379`, append-only persistence, healthcheck via `redis-cli ping`.

---

## 6. Data model (`app/models/f1_models.py`)

All models use SQLAlchemy 2.0 declarative style with UUID primary keys (`uuid.uuid4`) and `created_at` timestamps. The pgvector extension is enabled automatically in `init_db()`.

| Model | Purpose | Key fields |
|---|---|---|
| **Season** | A championship year | `year` (unique) |
| **Meeting** | A race weekend | `meeting_key` (OpenF1 key, unique), `meeting_name`, `circuit_short_name`, `country_name`, `date_start`, FK → `Season` |
| **Session** | A session within a meeting (Practice/Qualifying/Race) | `session_key` (OpenF1 key, unique), `session_name`, `session_type`, `date_start`, `date_end`, FK → `Meeting` |
| **Driver** | A driver entry for a specific session | `driver_number`, `broadcast_name`, `full_name`, `name_acronym`, `team_name`, `team_colour`, `country_code`, `headshot_url`, FK → `Session` |
| **Lap** | A single lap record | `driver_number`, `lap_number`, `lap_duration`, `i1_speed`, `i2_speed`, `st_speed`, `duration_sector_1/2/3`, `is_pit_out_lap`, `segments_sector_1/2/3` (JSON strings), `date_start`, FKs → `Session`, `Driver` |
| **PitStop** | A pit stop event | `driver_number`, `lap_number`, `pit_duration`, `date`, FK → `Session` |
| **RaceDocument** | Embedded documents for RAG | `session_key`, `doc_type`, `content`, `embedding` (`Vector(384)`, matches `all-MiniLM-L6-v2`), `metadata` (JSON string as `metadata_` column) |

### Relationships
- `Season` 1—N `Meeting`
- `Meeting` 1—N `Session`
- `Session` 1—N `Driver`, `Lap`, `PitStop`
- `Driver` 1—N `Lap`

### Notes for future work
- `RaceDocument.embedding` dimension (384) is tied to `all-MiniLM-L6-v2`. If a different embedding model is chosen later, this column must be migrated.
- `segments_sector_*` and `metadata_` are stored as raw JSON text — consider migrating to native `JSONB` columns in Phase 2 for queryability.
- No `Team` table yet — team info is denormalized onto `Driver`. Consider normalizing if cross-session team analytics are needed.

---

## 7. OpenF1 ingestion client (`ingestion/openf1.py`)

An async `httpx`-based client (`OpenF1Client`) wrapping `https://api.openf1.org/v1`, fully public (no key required). Implemented methods:

| Method | Endpoint | Purpose |
|---|---|---|
| `get_meetings(year=None)` | `/meetings` | List race weekends, optional year filter |
| `get_latest_meeting()` | `/meetings?meeting_key=latest` | Most recent race weekend |
| `get_sessions(meeting_key, session_type, year)` | `/sessions` | List sessions with filters |
| `get_latest_session()` | `/sessions?session_key=latest` | Most recent session |
| `get_drivers(session_key, driver_number=None)` | `/drivers` | Driver entries for a session |
| `get_laps(session_key, driver_number=None, lap_number=None)` | `/laps` | Lap data |
| `get_pit_stops(session_key, driver_number=None)` | `/pit` | Pit stop records |
| `get_car_data(session_key, driver_number)` | `/car_data` | High-frequency telemetry (~3.7Hz): throttle, brake, RPM, gear, speed, DRS |
| `get_position(session_key, driver_number=None)` | `/location` | x/y/z track position |
| `get_intervals(session_key)` | `/intervals` | Live gap-to-leader / gap-to-car-ahead |
| `get_race_control(session_key)` | `/race_control` | Flags, VSC, SC, penalties |

### CLI entry points
- `python ingestion/openf1.py` → `fetch_latest()`: prints latest meeting + session keys.
- `python ingestion/openf1.py <session_key>` → `ingest_session(session_key)`: fetches drivers, laps, pit stops, race control messages and **prints summaries** (does not yet write to DB — this is the core of Phase 2).

---

## 8. FastAPI application (`app/main.py`)

- App metadata: title `PITWALL·AI`, version `0.1.0`.
- **Lifespan handler**: calls `init_db()` on startup inside a try/except so the app degrades gracefully if Postgres is unreachable (prints a warning instead of crashing).
- **CORS**: currently allows `http://localhost:5173` (Vite dev server) for the future React frontend.
- **Routes implemented so far**:
  - `GET /` → welcome message
  - `GET /health` → `{"status": "ok", "version": "0.1.0", "project": "PITWALL·AI"}`

---

## 9. Database connection (`app/database.py`)

- `create_async_engine(settings.database_url, echo=settings.app_debug, pool_size=10, max_overflow=20)`
- `AsyncSessionLocal` — async session factory (`expire_on_commit=False`)
- `init_db()` — runs `CREATE EXTENSION IF NOT EXISTS vector` then `Base.metadata.create_all` (creates all tables if they don't exist)
- `get_db()` — FastAPI dependency yielding an `AsyncSession`, with rollback-on-exception and guaranteed close

---

## 10. Development roadmap

### ✅ Phase 1 — Foundation & Data Pipeline (complete)
- Docker Compose for Postgres (pgvector) + Redis
- SQLAlchemy async setup with `init_db()`
- Full data model: Season, Meeting, Session, Driver, Lap, PitStop, RaceDocument
- OpenF1 async client with full endpoint coverage
- FastAPI skeleton with graceful DB-degradation and `/health` endpoint
- Verified: server starts cleanly with and without Docker running

### 🔄 Phase 2 — Core FastAPI Backend (in progress)
Goal: a working backend testable via Postman/curl, with real data flowing into Postgres.
- [ ] Build a **repository / CRUD layer** (`app/repositories/` or `app/crud/`) for each model: upsert-by-key logic so re-ingesting a session doesn't create duplicates (use `meeting_key`, `session_key`, `driver_number + session_id`, etc. as natural keys)
- [ ] Extend `ingestion/openf1.py` (or a new `ingestion/pipeline.py`) so `ingest_session()` **writes** to the DB via the repository layer instead of just printing
- [ ] Add **Alembic** for migrations (initial migration should match current `Base.metadata`)
- [ ] Build REST routes in `app/api/`:
  - `GET /sessions` — list sessions (with filters: year, meeting, type)
  - `GET /sessions/{session_id}` — session detail incl. meeting + drivers
  - `GET /sessions/{session_id}/laps` — laps for a session (filter by driver_number)
  - `GET /sessions/{session_id}/drivers` — drivers for a session
  - `GET /sessions/{session_id}/pit-stops`
  - `POST /ingest/{session_key}` — trigger ingestion for a session (background task)
- [ ] Add Redis caching for frequently-read endpoints (e.g. live session state, latest session)
- [ ] Add a WebSocket endpoint for live session updates (foundation for live telemetry in Phase 5)
- [ ] Basic pytest coverage for repository functions and API routes

### Phase 3 — AI Agent Layer (LangGraph)
- LangGraph orchestrator node that routes natural-language queries to specialist agents
- **Strategy agent** — pit window analysis, tyre degradation modeling, undercut/overcut evaluation
- **Telemetry agent** — pace analysis, sector/speed-trap anomaly detection, comparative deltas, pit stop outlier detection (see detailed responsibilities discussed in project chat history)
- **RAG agent** — semantic search over `RaceDocument` embeddings
- **Commentary agent** — wraps structured agent outputs in natural-language briefings
- Requires `OPENAI_API_KEY` to be set in `.env`

### Phase 4 — RAG Pipeline + Embeddings
- Build an embedding pipeline using `sentence-transformers/all-MiniLM-L6-v2` to populate `RaceDocument.embedding`
- Source documents: race summaries, strategy notes, historical incident write-ups
- Wire the RAG agent to pgvector similarity search
- Target capability: answer questions like "Has a safety car at Monza ever changed a championship result?"

### Phase 5 — React Frontend
- Vite + React app in `frontend/`
- Three panels: live telemetry dashboard, strategy/pit-stop panel, AI intelligence chat
- Connect to FastAPI via REST (data) + WebSocket (live updates)

---

## 11. Conventions for continued development

- **Async everywhere** on the backend — all DB and HTTP I/O uses `async`/`await` (`asyncpg`, `httpx.AsyncClient`).
- **UUID primary keys** (`uuid.uuid4`) for all tables; OpenF1's own integer keys (`meeting_key`, `session_key`) are stored as separate unique columns for natural-key lookups during ingestion.
- **Settings via `app/config.py`** — never hardcode credentials or URLs; add new config to `Settings` and `.env`.
- **Graceful degradation** — features that depend on external services (Postgres, Redis, OpenAI) should not crash app startup; log a warning and continue where reasonable.
- **Windows/PowerShell environment** — when giving terminal commands, use PowerShell syntax (e.g. `venv\Scripts\python.exe`, not `source venv/bin/activate`).
- **OpenF1 is the source of truth for live/recent data**; Ergast/FastF1 (when integrated) will supplement historical depth.

---

## 12. Known issues / things to watch

- `greenlet` must be explicitly installed alongside SQLAlchemy async on Windows (`pip install greenlet`) — not always pulled in automatically.
- PowerShell execution policy may block `venv\Scripts\activate.ps1`; either run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` or call `venv\Scripts\python.exe` directly.
- `RaceDocument.embedding` dimension is hardcoded to 384 (`all-MiniLM-L6-v2`) — changing embedding models requires a migration.
- No authentication/authorization implemented yet — `SECRET_KEY` is a placeholder for future use.

---

## 13. Author / context

Built by Warisha Bilal (BS AI, UET Peshawar) as a flagship portfolio project, developed incrementally with an AI pair-programming workflow. This README is intended to give any AI coding agent (including Antigravity) full context to continue Phase 2 onward without losing architectural consistency with Phase 1.