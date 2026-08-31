# Phase 20 — FastAPI Backend Foundation

## Goal

Create a minimal, production-oriented FastAPI foundation before adding domain models, databases, RAG, agents, or cloud dependencies.

## Included

- Python 3.12 package configuration
- FastAPI
- Pydantic Settings
- structured JSON logging with structlog
- root endpoint
- health endpoint
- pytest
- Ruff
- mypy
- Dockerfile
- setup/verification script

## Commands

With `apps/api/.venv` active:

```powershell
.\scripts\setup_backend.ps1
```

Then:

```powershell
python -m uvicorn casemesh.main:app --app-dir apps/api/src --reload
```

Open:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```
