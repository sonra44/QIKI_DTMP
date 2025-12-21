@echo off
setlocal
pushd "%~dp0"

echo ===============================================
echo    QIKI Operator Console Launcher
echo ===============================================
echo.

echo Checking Docker services...
set "NATS_RUNNING="
for /f "usebackq delims=" %%i in (`docker ps --filter "name=qiki-nats-phase1" --format "{{.Names}}"`) do set "NATS_RUNNING=1"
if not defined NATS_RUNNING (
    echo Starting QIKI services...
    docker compose -f docker-compose.phase1.yml up -d nats q-sim-service q-sim-radar faststream-bridge
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

docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml run --rm --build operator-console

echo.
echo Console closed.
pause

popd
endlocal
