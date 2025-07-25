#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# =========================
# init_agent_env.sh
# Gemini Agent Init Script
# =========================

# Check for required tools
for tool in jq mkdir date; do
  if ! command -v "$tool" &>/dev/null; then
    echo "[ERROR] Required tool '$tool' is missing. Please install it."
    exit 1
  fi
done

# Setup log folder
TODAY=$(date +%Y-%m-%d)
LOG_DIR=".agent/logs/$TODAY"
mkdir -p "$LOG_DIR"
echo "[INFO] Log directory created at $LOG_DIR"

# Create placeholder log file
TASK_LOG_FILE="$LOG_DIR/task-001-response.md"
if [ ! -f "$TASK_LOG_FILE" ]; then
  echo "# Task 001 Response - $TODAY" > "$TASK_LOG_FILE"
  echo "[INFO] Placeholder log created: $TASK_LOG_FILE"
fi

# Ensure AGENT_ALIGNMENT.md exists
if [ ! -f "AGENT_ALIGNMENT.md" ]; then
  echo "[WARN] AGENT_ALIGNMENT.md not found. Please create or copy it from the template."\else
  echo "[OK] AGENT_ALIGNMENT.md found."
fi

# Ensure GEMINI_TASK_LOG.md exists
if [ ! -f "GEMINI_TASK_LOG.md" ]; then
  echo "[WARN] GEMINI_TASK_LOG.md not found. Please initialize or copy it."\else
  echo "[OK] GEMINI_TASK_LOG.md found."
fi

# Final status
echo "[SUCCESS] Agent environment initialized for $TODAY"
echo "[NEXT] You can now start using Gemini CLI or run a task."
exit 0
