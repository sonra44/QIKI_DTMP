#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  else
    PYTHON_BIN="${PYTHON:-python3}"
  fi
fi

cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

LOG_PATH="${INTROSPECTOR_TUI_LOG:-}"
EXIT_MARKER="${INTROSPECTOR_TUI_EXIT_MARKER:-}"

if ! "$PYTHON_BIN" -c "import textual" >/dev/null 2>&1; then
  cat >&2 <<EOF
[run_tui] Textual is not installed in PYTHON_BIN=$PYTHON_BIN
Use one of the supported setup paths before launching the interface:
  1. python -m venv .venv
  2. .venv/bin/pip install -e .[tui,service,dev]
  3. ./scripts/run_tui.sh
EOF
  exit 2
fi

if [[ -z "$LOG_PATH" && -z "$EXIT_MARKER" ]]; then
  exec "$PYTHON_BIN" -m project_introspector.tui_app
fi

if [[ -n "$LOG_PATH" ]]; then
  mkdir -p "$(dirname "$LOG_PATH")"
  "$PYTHON_BIN" -m project_introspector.tui_app >>"$LOG_PATH" 2>&1
else
  "$PYTHON_BIN" -m project_introspector.tui_app
fi
status=$?

if [[ -n "$EXIT_MARKER" ]]; then
  mkdir -p "$(dirname "$EXIT_MARKER")"
  printf '%s\n' "$status" >"$EXIT_MARKER"
fi

exit "$status"
