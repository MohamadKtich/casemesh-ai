$ErrorActionPreference = "Continue"

Write-Host "CaseMesh AI - Environment Check" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

function Check-Command {
    param(
        [string]$Name,
        [string]$Command
    )

    Write-Host ""
    Write-Host "[$Name]" -ForegroundColor Yellow

    try {
        Invoke-Expression $Command
    }
    catch {
        Write-Host "NOT AVAILABLE" -ForegroundColor Red
    }
}

Check-Command "Python 3.12" "py -3.12 --version"
Check-Command "Git" "git --version"

Check-Command "Node.js" "node --version"
Check-Command "npm" "npm --version"

Check-Command "Docker" "docker --version"
Check-Command "Docker Compose" "docker compose version"

Check-Command "Ollama" "ollama --version"

Check-Command "Azure CLI" "az version"
Check-Command "Azure Bicep" "az bicep version"

Check-Command "AWS CLI" "aws --version"

Write-Host ""
Write-Host "[Ollama Models]" -ForegroundColor Yellow

try {
    ollama list
}
catch {
    Write-Host "Could not read Ollama models." -ForegroundColor Red
}

Write-Host ""
Write-Host "Environment check complete." -ForegroundColor Green
