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

Write-Host "CaseMesh AI - Phase 25 Investigation Orchestration Setup" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

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

$modelName = "qwen3:8b"
$modelInstalled = ollama list | Select-String -Pattern "^qwen3:8b\s"

if (-not $modelInstalled) {
    Write-Host ""
    Write-Host "Pulling local generation model: $modelName" -ForegroundColor Yellow
    Invoke-Native { ollama pull $modelName } "Failed to pull the generation model"
}
else {
    Write-Host "Generation model already installed." -ForegroundColor Green
}

Write-Host ""
Write-Host "Installing Phase 25 backend dependencies..." -ForegroundColor Yellow
Invoke-Native {
    python -m pip install -e "apps/api[dev]"
} "Dependency installation failed"

Write-Host ""
Write-Host "LangGraph version:" -ForegroundColor Yellow
Invoke-Native {
    python -c "import importlib.metadata as m; print(m.version('langgraph'))"
} "LangGraph installation check failed"

Write-Host ""
Write-Host "Checking PostgreSQL..." -ForegroundColor Yellow
Invoke-Native { docker compose up -d postgres } "Failed to start PostgreSQL"

Write-Host ""
Write-Host "Applying Alembic migration 0004..." -ForegroundColor Yellow
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
Write-Host "Phase 25 investigation orchestration setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "Run the API with:"
Write-Host "python -m uvicorn casemesh.main:app --app-dir apps/api/src --reload"
Write-Host ""
Write-Host "Then validate:"
Write-Host "POST /cases/{case_id}/investigations"
Write-Host "GET  /cases/{case_id}/investigations/{workflow_id}"
Write-Host "GET  /cases/{case_id}/investigations"
