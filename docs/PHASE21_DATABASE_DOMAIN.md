# Phase 21 — PostgreSQL, pgvector, Domain Models, Alembic

## Purpose

This milestone adds the persistent system-of-record foundation for CaseMesh AI.

## Local database

PostgreSQL 16 with pgvector runs locally through Docker Compose.

No cloud database is required for this milestone.

## Included

- PostgreSQL
- pgvector
- SQLAlchemy 2.x async
- asyncpg
- Alembic
- core domain tables
- repository/service layers
- case CRUD API
- database readiness endpoint
- duplicate case-number handling with HTTP 409 Conflict

## Domain tables

- users
- cases
- case_documents
- policies
- evidence
- investigation_runs
- resolution_drafts
- approvals
- action_requests
- audit_events
- provider_calls
- cost_records

## Setup

With Docker Desktop running and the Python 3.12 venv active:

```powershell
.\scripts\setup_database.ps1
```

Then run:

```powershell
python -m uvicorn casemesh.main:app --app-dir apps/api/src --reload
```

Validate:

```text
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/health/ready
GET http://127.0.0.1:8000/docs
```

Swagger exposes:

- POST /cases
- GET /cases
- GET /cases/{case_id}
- PATCH /cases/{case_id}

Creating a duplicate `case_number` returns:

```text
409 Conflict
```

with a clear API error instead of an internal server error.

## Stop database

```powershell
.\scripts\stop_database.ps1
```

## Reset local database

Destructive:

```powershell
.\scripts\reset_database.ps1
```
