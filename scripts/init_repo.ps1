$ErrorActionPreference = "Stop"

Write-Host "Initializing CaseMesh AI Git repository..." -ForegroundColor Cyan

if (Test-Path ".git") {
    Write-Host "Git repository already initialized." -ForegroundColor Yellow
} else {
    git init
    git branch -M main
}

git add .
git status

Write-Host ""
Write-Host "Review the staged files above." -ForegroundColor Yellow
Write-Host "When ready, create the first commit with:" -ForegroundColor Green
Write-Host 'git commit -m "chore: initialize CaseMesh AI repository"'
