$ErrorActionPreference = "Stop"


function Invoke-CheckedCommand {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Description,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,

        [Parameter(Mandatory = $true)]
        [string]$FailureMessage
    )

    Write-Host ""
    Write-Host $Description -ForegroundColor Yellow

    & $Command

    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (exit code $LASTEXITCODE)"
    }
}


Write-Host ""
Write-Host "CaseMesh AI - Phase 26 HITL + Policy Guardrails Setup" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""


# ------------------------------------------------------------
# 1. Validate Python environment
# ------------------------------------------------------------

Invoke-CheckedCommand `
    -Description "Checking Python environment..." `
    -Command {
        python --version
    } `
    -FailureMessage "Python environment check failed"


# ------------------------------------------------------------
# 2. Install / refresh API dependencies
# ------------------------------------------------------------

Invoke-CheckedCommand `
    -Description "Installing Phase 26 dependencies..." `
    -Command {
        python -m pip install -e ".\apps\api"
    } `
    -FailureMessage "Dependency installation failed"


# ------------------------------------------------------------
# 3. Confirm LangGraph packages
# ------------------------------------------------------------

Invoke-CheckedCommand `
    -Description "Checking LangGraph installation..." `
    -Command {
        python -c "import langgraph; print('LangGraph available.')"
    } `
    -FailureMessage "LangGraph check failed"


Invoke-CheckedCommand `
    -Description "Checking LangGraph PostgreSQL checkpoint package..." `
    -Command {
        python -c "from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver; print('LangGraph PostgreSQL checkpoint package available.')"
    } `
    -FailureMessage "LangGraph PostgreSQL checkpoint package check failed"


# ------------------------------------------------------------
# 4. Start PostgreSQL
# ------------------------------------------------------------

Invoke-CheckedCommand `
    -Description "Checking PostgreSQL..." `
    -Command {
        docker compose up -d postgres
    } `
    -FailureMessage "PostgreSQL startup failed"


# ------------------------------------------------------------
# 5. Apply database migrations
# ------------------------------------------------------------

Invoke-CheckedCommand `
    -Description "Applying Alembic migration 0005..." `
    -Command {
        python -m alembic -c apps/api/alembic.ini upgrade head
    } `
    -FailureMessage "Alembic migration failed"


# ------------------------------------------------------------
# 6. Initialize durable LangGraph PostgreSQL checkpoint tables
#
# Windows:
# psycopg async cannot run using ProactorEventLoop.
# Force WindowsSelectorEventLoopPolicy before asyncio.run().
#
# setup_checkpointer requires the CaseMesh Settings instance.
# ------------------------------------------------------------

Write-Host ""
Write-Host "Initializing durable LangGraph checkpoint tables..." -ForegroundColor Yellow

$checkpointSetup = @'
import asyncio
import sys


if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )


from casemesh.core.config import get_settings
from casemesh.workflows.checkpoints import setup_checkpointer


settings = get_settings()


asyncio.run(
    setup_checkpointer(settings)
)


print("LangGraph PostgreSQL checkpoint tables initialized.")
'@

$checkpointSetup | python -

if ($LASTEXITCODE -ne 0) {
    throw "LangGraph checkpoint setup failed (exit code $LASTEXITCODE)"
}


# ------------------------------------------------------------
# 7. Ruff formatting
# ------------------------------------------------------------

Invoke-CheckedCommand `
    -Description "Running Ruff formatter..." `
    -Command {
        python -m ruff format apps/api
    } `
    -FailureMessage "Ruff formatting failed"


# ------------------------------------------------------------
# 8. Ruff linting
# ------------------------------------------------------------

Invoke-CheckedCommand `
    -Description "Running Ruff checks..." `
    -Command {
        python -m ruff check apps/api
    } `
    -FailureMessage "Ruff linting failed"


# ------------------------------------------------------------
# 9. Static type checking
# ------------------------------------------------------------

Invoke-CheckedCommand `
    -Description "Running mypy..." `
    -Command {
        python -m mypy apps/api/src apps/api/tests
    } `
    -FailureMessage "mypy failed"


# ------------------------------------------------------------
# 10. Automated tests
# ------------------------------------------------------------

Invoke-CheckedCommand `
    -Description "Running pytest..." `
    -Command {
        python -m pytest apps/api/tests
    } `
    -FailureMessage "pytest failed"


# ------------------------------------------------------------
# Complete
# ------------------------------------------------------------

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "Phase 26 HITL + policy guardrails setup complete." -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""

Write-Host "Validated:" -ForegroundColor Cyan
Write-Host "  - Phase 26 dependencies" -ForegroundColor Green
Write-Host "  - LangGraph" -ForegroundColor Green
Write-Host "  - LangGraph PostgreSQL checkpoint package" -ForegroundColor Green
Write-Host "  - PostgreSQL" -ForegroundColor Green
Write-Host "  - Alembic migration 0005" -ForegroundColor Green
Write-Host "  - Durable LangGraph PostgreSQL checkpointing" -ForegroundColor Green
Write-Host "  - Ruff formatting" -ForegroundColor Green
Write-Host "  - Ruff linting" -ForegroundColor Green
Write-Host "  - mypy" -ForegroundColor Green
Write-Host "  - pytest" -ForegroundColor Green
Write-Host ""

Write-Host "Do not start the API server yet." -ForegroundColor Yellow
Write-Host ""