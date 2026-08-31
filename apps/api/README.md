# CaseMesh AI API

FastAPI backend foundation for CaseMesh AI.

## Local development

From the repository root with the Python 3.12 virtual environment active:

```powershell
python -m pip install --upgrade pip
python -m pip install -e "apps/api[dev]"
```

Run quality checks:

```powershell
python -m ruff check apps/api
python -m ruff format --check apps/api
python -m mypy apps/api/src apps/api/tests
python -m pytest apps/api/tests
```

Run the API:

```powershell
python -m uvicorn casemesh.main:app --app-dir apps/api/src --reload
```

Endpoints:

- `GET /`
- `GET /health`
- `GET /docs`
