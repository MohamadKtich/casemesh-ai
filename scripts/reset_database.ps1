$ErrorActionPreference = "Stop"

Write-Host "WARNING: This deletes the local CaseMesh PostgreSQL volume." -ForegroundColor Yellow
docker compose down -v
Write-Host "Local database volume removed." -ForegroundColor Green
