$ErrorActionPreference = "Stop"

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (exit code $LASTEXITCODE)"
    }
}

Write-Host "CaseMesh AI - Phase 22 Ingestion Setup" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

$pythonVersion = python --version
if ($pythonVersion -notmatch "Python 3\.12") {
    throw "The active Python must be 3.12. Activate apps\api\.venv first."
}

Write-Host ""
Write-Host "Starting PostgreSQL..." -ForegroundColor Yellow
Invoke-Native { docker compose up -d postgres } "Failed to start PostgreSQL"

Write-Host ""
Write-Host "Installing Phase 22 dependencies..." -ForegroundColor Yellow
Invoke-Native { python -m pip install -e "apps/api[dev]" } "Dependency installation failed"

Write-Host ""
Write-Host "Applying Alembic migrations..." -ForegroundColor Yellow
Invoke-Native { python -m alembic -c apps/api/alembic.ini upgrade head } "Alembic failed"

New-Item -ItemType Directory -Force -Path "data\raw\cases" | Out-Null

Write-Host ""
Write-Host "Running quality checks..." -ForegroundColor Yellow
Invoke-Native { python -m ruff format apps/api } "Ruff formatting failed"
Invoke-Native { python -m ruff check apps/api } "Ruff linting failed"
Invoke-Native { python -m mypy apps/api/src apps/api/tests } "mypy failed"
Invoke-Native { python -m pytest apps/api/tests } "pytest failed"

Write-Host ""
Write-Host "Phase 22 ingestion foundation setup complete." -ForegroundColor Green
Write-Host "Run the API with:"
Write-Host "python -m uvicorn casemesh.main:app --app-dir apps/api/src --reload"
