@echo off
echo ===============================================
echo    QIKI Operator Console Launcher
echo ===============================================
echo.

echo Checking Docker services...
docker ps --filter "name=qiki-nats-phase1" --format "{{.Names}}" > nul 2>&1
if errorlevel 1 (
    echo Starting QIKI services...
    docker compose up -d nats q-sim-service q-sim-radar faststream-bridge
    timeout /t 5 > nul
)

echo Starting QIKI Operator Console...
echo.
echo ===== CONTROLS =====
echo Ctrl+Q - Quit
echo Ctrl+T - Telemetry
echo Ctrl+C - Chat
echo Ctrl+D - Dark mode
echo F1     - Help
echo ====================
echo.

docker run -it --rm ^
    --network qiki_dtmp_local_qiki-network-phase1 ^
    -e NATS_URL=nats://qiki-nats-phase1:4222 ^
    -e GRPC_HOST=qiki-sim-phase1 ^
    -e GRPC_PORT=50051 ^
    -e TERM=xterm-256color ^
    -e COLORTERM=truecolor ^
    --name qiki-operator-console-interactive ^
    qiki-operator-console:latest ^
    python main.py

echo.
echo Console closed.
pause