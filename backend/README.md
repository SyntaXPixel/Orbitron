# Orbitron — Backend Service

The Orbitron backend is the authoritative application service for coordinating satellite downlink requests across a shared ground-station network. It validates operational requests, stores state, coordinates scheduling and security, and exposes consistent information to the frontend console.

## Architecture

- **Framework:** FastAPI with Python 3.11+
- **Persistence:** SQLAlchemy 2 with SQLite in WAL mode and foreign-key enforcement
- **Migrations:** Alembic
- **Validation:** Pydantic v2 matching `orbitron.v1` shared contract
- **Authentication:** Backend-managed session tokens, Argon2 password hashing, CSRF tokens, and scoped service bearer credentials
- **Execution Model:** Asyncio background operations worker processing a persistent SQLite operation queue

## Directory Structure

```text
backend/
├── app/
│   ├── main.py                  # FastAPI app entry point and error envelopes
│   ├── config.py                # Environment configuration
│   ├── lifespan.py              # Application lifespan & worker lifecycle
│   ├── db/
│   │   ├── session.py           # SQLite connection & sessionmaker
│   │   ├── models.py            # SQLAlchemy relational schema
│   │   └── migrations/          # Alembic migrations
│   ├── schemas/
│   │   ├── public.py            # Shared orbitron.v1 JSON contract schemas
│   │   ├── requests.py          # HTTP mutation request models
│   │   ├── ingestion.py         # Service & simulator ingestion payloads
│   │   └── errors.py            # Standardized API error envelopes
│   ├── routes/                  # API route handlers (/api/v1/...)
│   ├── services/                # Business logic, validation & accounting
│   ├── adapters/                # Adapters for Scheduler, Security, Simulator
│   ├── workers/                 # Persisted asynchronous operations worker
│   └── cli/                     # Bootstrap & OpenAPI export CLI commands
├── fixtures/                    # Seed scenarios
├── tests/                       # Complete automated Pytest suite (29 tests)
├── alembic.ini                  # Migration configuration
├── pyproject.toml               # Build & dependency declarations
├── requirements.lock            # Pinned reproducible dependencies
├── .env.example                 # Environment variables template
├── README.md                    # This document
└── IMPLEMENTATION_REPORT.md     # Handover & verification report
```

## Quickstart & Local Setup

### 1. Requirements

- Python 3.11 or newer
- Virtual environment (recommended)

### 2. Install Dependencies

```bash
cd backend
python -m pip install -r requirements.lock
```

### 3. Run Migrations

```bash
python -m alembic upgrade head
```

### 4. Bootstrap Demonstration Dataset

```bash
python -m app.cli.bootstrap
```

This creates:
- Two demonstration organizations (`org-alpha`, `org-beta`)
- Network administrator and mission operator user accounts
- Service identities with scoped bearer credentials (saved to ignored `.runtime/service_credentials.json`)
- Satellites, ground stations, antennas, and initial communication opportunities
- Initial deterministic scenario (`scenario-001`, seed 42)

### 5. Start Backend Server

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The API will be available at `http://localhost:8000/api/v1`.

### 6. Run Automated Tests

```bash
python -m pytest -v
```

### 7. Export OpenAPI Schema

```bash
python -m app.cli.export_openapi
```
Exports OpenAPI 3.1 JSON definition to `backend/.runtime/openapi.json`.

## Demo Credentials

| Role | Email | Password | Organization |
|---|---|---|---|
| Network Admin | `admin@orbitron.local` | `AdminPassword123!` | Alpha Space Dynamics |
| Alpha Operator | `operator@alpha.local` | `AlphaOperator123!` | Alpha Space Dynamics |
| Beta Operator | `operator@beta.local` | `BetaOperator123!` | Beta Orbital Communications |

Service bearer tokens are stored in `backend/.runtime/service_credentials.json` upon running `app.cli.bootstrap`.

## Integration Boundaries

- **Scheduler Adapter (`app/adapters/scheduler.py`):** Automatically imports `scheduler.api` when available. If not available, gracefully reports degraded status and rejects schedule execution with `503 SCHEDULER_UNAVAILABLE` rather than manufacturing fake results.
- **Security Adapter (`app/adapters/security.py`):** Coordinates with `security.api` when installed.
- **External Simulation:** Communicates strictly via authenticated HTTP endpoints under `/api/v1/ingest/...`.
