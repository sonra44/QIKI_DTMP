#!/usr/bin/env pwsh
# Скрипт для запуска QIKI Operator Console

Write-Host "🚀 Запускаем QIKI Operator Console..." -ForegroundColor Cyan

# Проверяем, запущены ли основные сервисы
$natsRunning = docker ps --filter "name=qiki-nats-phase1" --format "{{.Names}}"
if (-not $natsRunning) {
    Write-Host "⚠️  Основные сервисы QIKI не запущены. Запускаем..." -ForegroundColor Yellow
    docker compose up -d nats q-sim-service q-sim-radar faststream-bridge
    Start-Sleep -Seconds 5
}

Write-Host "📡 Подключаемся к системе QIKI..." -ForegroundColor Green

# Запускаем консоль в интерактивном режиме
docker run -it --rm `
    --network qiki_dtmp_local_qiki-network-phase1 `
    -e NATS_URL=nats://qiki-nats-phase1:4222 `
    -e GRPC_HOST=qiki-sim-phase1 `
    -e GRPC_PORT=50051 `
    -e TERM=xterm-256color `
    -e COLORTERM=truecolor `
    --name qiki-operator-console-interactive `
    qiki-operator-console:latest `
    python main.py

Write-Host "✅ Консоль завершила работу" -ForegroundColor Green