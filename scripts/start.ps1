# Запуск AeonBiblio Backend (Windows)

Set-Location $PSScriptRoot\..

if (-not (Test-Path .env)) {
    Write-Host "Файл .env не найден. Копирую из .env.example..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "Отредактируйте .env (SECRET_KEY, пароли) и запустите снова." -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting AeonBiblio (db + minio + api)..." -ForegroundColor Cyan
docker compose up --build
