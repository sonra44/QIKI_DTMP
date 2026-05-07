#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python}"
export PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONDONTWRITEBYTECODE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"

RUN_ROOT="${RUN_ROOT:-tmp/release_gate_runs}"
CLI_RUN_ROOT="${CLI_RUN_ROOT:-tmp/release_gate_cli_runs}"
PROJECT_NAME="${PROJECT_NAME:-INTROSPECTOR_DEMO}"

mkdir -p "$RUN_ROOT" "$CLI_RUN_ROOT"

echo "[gate] compileall"
"$PYTHON_BIN" -m compileall -q src analyzer scripts tests

echo "[gate] pytest"
"$PYTHON_BIN" -m pytest -q tests

echo "[gate] direct offline run"
"$PYTHON_BIN" scripts/run_full_local_analysis.py \
  --project-name "$PROJECT_NAME" \
  --source-root src \
  --out-dir "$RUN_ROOT" \
  --offline | tee tmp/release_gate_direct_run.log
DIRECT_RUN_DIR="$(awk -F': ' '/Run directory:/ {print $2}' tmp/release_gate_direct_run.log | tail -n 1)"
test -n "$DIRECT_RUN_DIR"

echo "[gate] direct validate"
"$PYTHON_BIN" scripts/validate_run_result.py "$DIRECT_RUN_DIR"

echo "[gate] cli offline run"
"$PYTHON_BIN" -m project_introspector.cli run \
  --project-name "$PROJECT_NAME" \
  --source-root src \
  --out-dir "$CLI_RUN_ROOT" \
  --offline | tee tmp/release_gate_cli_run.log
CLI_RUN_DIR="$(awk -F': ' '/Run directory:/ {print $2}' tmp/release_gate_cli_run.log | tail -n 1)"
test -n "$CLI_RUN_DIR"

echo "[gate] cli validate"
"$PYTHON_BIN" -m project_introspector.cli validate "$CLI_RUN_DIR"

if command -v tmux >/dev/null 2>&1; then
  echo "[gate] tmux smoke"
  bash scripts/tui_tmux_smoke.sh
else
  echo "[gate] tmux smoke skipped: tmux not installed"
fi

echo "RELEASE_TEST_GATE_OK"
