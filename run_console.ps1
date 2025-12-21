#!/usr/bin/env pwsh
# Скрипт для запуска QIKI Operator Console

Set-Location -LiteralPath $PSScriptRoot

Write-Host "🚀 Запускаем QIKI Operator Console..." -ForegroundColor Cyan

# Проверяем, запущены ли основные сервисы
$natsRunning = docker ps --filter "name=qiki-nats-phase1" --format "{{.Names}}"
if (-not $natsRunning) {
    Write-Host "⚠️  Основные сервисы QIKI не запущены. Запускаем..." -ForegroundColor Yellow
    docker compose -f docker-compose.phase1.yml up -d nats q-sim-service q-sim-radar faststream-bridge
    Start-Sleep -Seconds 5
}

Write-Host "📡 Подключаемся к системе QIKI..." -ForegroundColor Green

# Запускаем консоль в интерактивном режиме (overlay поверх Phase1)
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml run --rm --build operator-console

Write-Host "✅ Консоль завершила работу" -ForegroundColor Green
