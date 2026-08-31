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

Write-Host "CaseMesh AI - Database Setup" -ForegroundColor Cyan
Write-Host "============================" -ForegroundColor Cyan

Write-Host ""
Write-Host "Starting PostgreSQL + pgvector..." -ForegroundColor Yellow
Invoke-Native { docker compose up -d postgres } "Failed to start PostgreSQL"

Write-Host ""
Write-Host "Waiting for database health..." -ForegroundColor Yellow

$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    $status = docker inspect --format='{{.State.Health.Status}}' casemesh-postgres 2>$null
    if ($LASTEXITCODE -eq 0 -and $status -eq "healthy") {
        $healthy = $true
        break
    }
    Start-Sleep -Seconds 2
}

if (-not $healthy) {
    throw "PostgreSQL did not become healthy in time."
}

Write-Host "Database is healthy." -ForegroundColor Green

Write-Host ""
Write-Host "Installing Phase 21 dependencies..." -ForegroundColor Yellow
Invoke-Native { python -m pip install -e "apps/api[dev]" } "Dependency installation failed"

Write-Host ""
Write-Host "Running Alembic migrations..." -ForegroundColor Yellow
Invoke-Native { python -m alembic -c apps/api/alembic.ini upgrade head } "Alembic migration failed"

Write-Host ""
Write-Host "Running quality checks..." -ForegroundColor Yellow
Invoke-Native { python -m ruff format apps/api } "Ruff formatting failed"
Invoke-Native { python -m ruff check apps/api } "Ruff linting failed"
Invoke-Native { python -m mypy apps/api/src apps/api/tests } "mypy failed"
Invoke-Native { python -m pytest apps/api/tests } "pytest failed"

Write-Host ""
Write-Host "Phase 21 database setup complete." -ForegroundColor Green
Write-Host "Run the API with:"
Write-Host "python -m uvicorn casemesh.main:app --app-dir apps/api/src --reload"
