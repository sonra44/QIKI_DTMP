#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Get the directory of the current script
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

Q_SIM_SERVICE_PATH="$PROJECT_ROOT/services/q_sim_service/main.py"
Q_CORE_AGENT_PATH="$PROJECT_ROOT/services/q_core_agent/main.py"

LOG_DIR="$PROJECT_ROOT/.agent/logs/$(date +%Y-%m-%d)"
mkdir -p "$LOG_DIR"

Q_SIM_LOG="$LOG_DIR/q_sim_service.log"
Q_CORE_LOG="$LOG_DIR/q_core_agent.log"

echo "Starting Q-Sim Service..."
python3 "$Q_SIM_SERVICE_PATH" > "$Q_SIM_LOG" 2>&1 &
Q_SIM_PID=$!
echo "Q-Sim Service started with PID: $Q_SIM_PID (Log: $Q_SIM_LOG)"

sleep 2 # Give Q-Sim a moment to start

echo "Starting Q-Core Agent..."
python3 "$Q_CORE_AGENT_PATH" > "$Q_CORE_LOG" 2>&1 &
Q_CORE_PID=$!
echo "Q-Core Agent started with PID: $Q_CORE_PID (Log: $Q_CORE_LOG)"

echo "
QIKI Demo is running in the background.
To stop the services, run: kill $Q_SIM_PID $Q_CORE_PID
Logs are available in $LOG_DIR
"

wait $Q_SIM_PID $Q_CORE_PID
