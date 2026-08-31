$ErrorActionPreference = "Stop"

docker compose stop postgres
Write-Host "CaseMesh PostgreSQL stopped." -ForegroundColor Green
