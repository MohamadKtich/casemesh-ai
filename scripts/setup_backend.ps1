$ErrorActionPreference = "Stop"

Write-Host "CaseMesh AI - Backend Setup" -ForegroundColor Cyan
Write-Host "===========================" -ForegroundColor Cyan

$pythonVersion = python --version
Write-Host "Using $pythonVersion"

if ($pythonVersion -notmatch "Python 3\.12") {
    throw "The active Python must be 3.12. Activate apps\api\.venv first."
}

Write-Host ""
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

Write-Host ""
Write-Host "Installing backend and development dependencies..." -ForegroundColor Yellow
python -m pip install -e "apps/api[dev]"

Write-Host ""
Write-Host "Running Ruff..." -ForegroundColor Yellow
python -m ruff check apps/api
python -m ruff format --check apps/api

Write-Host ""
Write-Host "Running mypy..." -ForegroundColor Yellow
python -m mypy apps/api/src apps/api/tests

Write-Host ""
Write-Host "Running pytest..." -ForegroundColor Yellow
python -m pytest apps/api/tests

Write-Host ""
Write-Host "Backend foundation setup complete." -ForegroundColor Green
Write-Host "Run the API with:"
Write-Host "python -m uvicorn casemesh.main:app --app-dir apps/api/src --reload"
