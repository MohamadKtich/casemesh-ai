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

Write-Host "CaseMesh AI - Phase 23 Hybrid Retrieval Setup" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

$pythonVersion = python --version
if ($pythonVersion -notmatch "Python 3\.12") {
    throw "The active Python must be 3.12. Activate apps\api\.venv first."
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "Ollama is not available on PATH."
}

Write-Host ""
Write-Host "Checking Ollama service..." -ForegroundColor Yellow

try {
    $null = Invoke-RestMethod `
        -Uri "http://127.0.0.1:11434/api/tags" `
        -Method Get `
        -TimeoutSec 10
}
catch {
    throw "Ollama is installed but its local service is not reachable. Open Ollama, then run this script again."
}

$modelName = "nomic-embed-text"
$modelInstalled = ollama list | Select-String -Pattern "^$modelName(:latest)?\s"

if (-not $modelInstalled) {
    Write-Host ""
    Write-Host "Pulling local embedding model: $modelName" -ForegroundColor Yellow
    Write-Host "This is a one-time local download." -ForegroundColor DarkGray
    Invoke-Native { ollama pull $modelName } "Failed to pull the embedding model"
}
else {
    Write-Host "Embedding model already installed." -ForegroundColor Green
}

Write-Host ""
Write-Host "Starting PostgreSQL..." -ForegroundColor Yellow
Invoke-Native { docker compose up -d postgres } "Failed to start PostgreSQL"

Write-Host ""
Write-Host "Applying Alembic migration 0003..." -ForegroundColor Yellow
Invoke-Native {
    python -m alembic -c apps/api/alembic.ini upgrade head
} "Alembic failed"

Write-Host ""
Write-Host "Running quality checks..." -ForegroundColor Yellow
Invoke-Native { python -m ruff format apps/api } "Ruff formatting failed"
Invoke-Native { python -m ruff check apps/api } "Ruff linting failed"
Invoke-Native {
    python -m mypy apps/api/src apps/api/tests
} "mypy failed"
Invoke-Native { python -m pytest apps/api/tests } "pytest failed"

Write-Host ""
Write-Host "Phase 23 hybrid retrieval foundation setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "Run the API with:"
Write-Host "python -m uvicorn casemesh.main:app --app-dir apps/api/src --reload"
Write-Host ""
Write-Host "Then validate:"
Write-Host "GET  /embeddings/health"
Write-Host "POST /cases/{case_id}/documents/{document_id}/embed"
Write-Host "POST /cases/{case_id}/retrieval/search"
