#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="unconfigured"
PORT="8015"
SESSION=""
SESSION_CREATED=0
ANALYZER_WINDOW_NAME="INTROSPECTOR_SMOKE_ANALYZER_$$"
TUI_WINDOW_NAME="INTROSPECTOR_SMOKE_TUI_$$"
PROJECT_NAME="${PROJECT_NAME:-INTROSPECTOR_DEMO}"
HOST="${HOST:-127.0.0.1}"
PYTHON_BIN="${PYTHON_BIN:-}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-25}"
MODULE_PROBE="${MODULE_PROBE:-}"
SOURCE_ROOT="${INTROSPECTOR_SOURCE_ROOT:-}"

has_provider_credentials() {
  [[ -n "${OPENROUTER_API_KEY:-}" ]] \
    || [[ -n "${INTROSPECTOR_API_KEY:-}" ]] \
    || [[ -n "${LLM_PROVIDER_API_KEY:-}" ]] \
    || [[ -n "${INCEPTION_API_KEY:-}" ]]
}

usage() {
  cat >&2 <<'EOF'
Usage:
  scripts/tui_tmux_smoke.sh [--mode configured|unconfigured|live] [--port 8015] [--session name] [--project-name name]

Operational smoke only:
- creates a dedicated tmux session or uses the current attached session
- starts analyzer in one window
- starts the Textual TUI in another window
- captures pane output
- verifies analyzer/TUI startup without brittle snapshot testing
- mode=live reuses an existing analyzer instead of starting or scanning one
EOF
  exit 64
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --project-name)
      PROJECT_NAME="$2"
      shift 2
      ;;
    --session)
      SESSION="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      ;;
  esac
done

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed; skipping tmux smoke path." >&2
  exit 69
fi

if [[ -n "${TMUX:-}" && -z "$SESSION" ]]; then
  SESSION="$(tmux display-message -p '#S')"
  ORIGINAL_WINDOW_TARGET="$(tmux display-message -p '#{window_id}')"
elif [[ "$MODE" == "live" && -z "$SESSION" ]]; then
  SESSION="0"
elif [[ -z "$SESSION" ]]; then
  SESSION="introspector-smoke-$$"
fi

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  else
    PYTHON_BIN="${PYTHON:-python3}"
  fi
fi

if [[ "$MODE" == "configured" ]] && ! has_provider_credentials; then
  echo "configured tmux smoke requires provider credentials in the current shell environment" >&2
  exit 3
fi
if [[ "$MODE" != "configured" && "$MODE" != "unconfigured" && "$MODE" != "live" ]]; then
  echo "Unknown mode: $MODE" >&2
  usage
fi

cleanup() {
  if [[ "$SESSION_CREATED" == "1" ]]; then
    tmux kill-session -t "${SESSION:-}" >/dev/null 2>&1 || true
    return
  fi
  tmux select-window -t "${ORIGINAL_WINDOW_TARGET:-}" >/dev/null 2>&1 || true
  tmux kill-window -t "${TUI_WINDOW_TARGET:-}" >/dev/null 2>&1 || true
  tmux kill-window -t "${ANALYZER_WINDOW_TARGET:-}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

shell_quote() {
  printf "%q" "$1"
}

append_export_if_set() {
  local name="$1"
  local value="${!name:-}"
  if [[ -n "$value" ]]; then
    ANALYZER_CMD+="export ${name}=$(shell_quote "$value") && "
  fi
}

wait_for_status() {
  local deadline=$((SECONDS + TIMEOUT_SECONDS))
  local url="http://${HOST}:${PORT}/llm/status"
  while (( SECONDS < deadline )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

pane_exists() {
  local target="$1"
  tmux display-message -p -t "$target" '#{pane_id}' >/dev/null 2>&1
}

capture_window() {
  local target="$1"
  local lines="${2:--120}"
  if pane_exists "$target"; then
    capture_tui_pane "$target" "$lines"
  fi
}

capture_tui_pane() {
  local target="$1"
  local lines="${2:--120}"
  local capture
  if capture="$(tmux capture-pane -aep -t "$target" -S "$lines" 2>/dev/null)"; then
    if grep -q '[^[:space:]]' <<<"$capture"; then
      printf '%s\n' "$capture"
      return 0
    fi
  fi
  tmux capture-pane -p -t "$target" -S "$lines"
}

wait_for_tui_capture() {
  local target="$1"
  local deadline=$((SECONDS + TIMEOUT_SECONDS))
  while (( SECONDS < deadline )); do
    if ! pane_exists "$target"; then
      return 1
    fi
    local pane_meta
    pane_meta="$(tmux display-message -p -t "$target" '#{pane_dead} #{pane_current_command}')"
    if [[ "$pane_meta" == 1* ]]; then
      return 1
    fi
    local capture
    capture="$(capture_tui_pane "$target" -120)"
    if grep -q "\[TUI_EXIT " <<<"$capture" || [[ "$pane_meta" == *" sleep" ]]; then
      return 1
    fi
    if grep -q "module_path:" <<<"$capture" && grep -Eq 'source_path:|enrichment:' <<<"$capture"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

if [[ "$MODE" != "live" ]]; then
  ANALYZER_CMD="cd $(shell_quote "$ROOT_DIR") && "
  if [[ "$MODE" == "configured" ]]; then
    append_export_if_set OPENROUTER_API_KEY
    append_export_if_set OPENROUTER_MODEL
    append_export_if_set OPENROUTER_FALLBACK_MODEL
    append_export_if_set OPENROUTER_APP_NAME
    append_export_if_set OPENROUTER_HTTP_REFERER
    append_export_if_set INTROSPECTOR_PROVIDER
    append_export_if_set INTROSPECTOR_API_KEY
    append_export_if_set INTROSPECTOR_BASE_URL
    append_export_if_set INTROSPECTOR_MODEL
    append_export_if_set INTROSPECTOR_FALLBACK_MODEL
    append_export_if_set LLM_PROVIDER_NAME
    append_export_if_set LLM_PROVIDER_API_KEY
    append_export_if_set LLM_PROVIDER_BASE_URL
    append_export_if_set LLM_PROVIDER_MODEL
    append_export_if_set LLM_PROVIDER_FALLBACK_MODEL
    append_export_if_set INCEPTION_API_KEY
    append_export_if_set INCEPTION_BASE_URL
    append_export_if_set INCEPTION_MODEL
    append_export_if_set INCEPTION_FALLBACK_MODEL
  else
    ANALYZER_CMD+="unset OPENROUTER_API_KEY INTROSPECTOR_API_KEY LLM_PROVIDER_API_KEY INCEPTION_API_KEY && export ALLOW_DEGRADED_START=1 && "
  fi
  ANALYZER_CMD+="export HOST=$(shell_quote "$HOST") PORT=$(shell_quote "$PORT") PYTHON_BIN=$(shell_quote "$PYTHON_BIN") && ./scripts/run_fresh_analyzer.sh"

  if ! tmux has-session -t "$SESSION" >/dev/null 2>&1; then
    ANALYZER_META="$(tmux new-session -d -P -F '#{session_name} #{window_id} #{pane_id}' -s "$SESSION" -n "$ANALYZER_WINDOW_NAME" "$ANALYZER_CMD")"
    SESSION_CREATED=1
    ANALYZER_WINDOW_TARGET="$(printf '%s' "$ANALYZER_META" | awk '{print $2}')"
    ANALYZER_PANE_TARGET="$(printf '%s' "$ANALYZER_META" | awk '{print $3}')"
  else
    ANALYZER_META="$(tmux new-window -d -P -F '#{window_id} #{pane_id}' -t "$SESSION:" -n "$ANALYZER_WINDOW_NAME" "$ANALYZER_CMD")"
    ANALYZER_WINDOW_TARGET="${ANALYZER_META%% *}"
    ANALYZER_PANE_TARGET="${ANALYZER_META##* }"
  fi
fi
if ! wait_for_status; then
  echo "Analyzer did not expose /llm/status within ${TIMEOUT_SECONDS}s" >&2
  if [[ -n "${ANALYZER_PANE_TARGET:-}" ]]; then
    capture_window "$ANALYZER_PANE_TARGET" -80 >&2 || true
  fi
  exit 10
fi

STATUS_JSON="$(curl -fsS "http://${HOST}:${PORT}/llm/status")"
if [[ "$MODE" != "live" ]]; then
  SCAN_CMD="cd $(shell_quote "$ROOT_DIR") && $(shell_quote "$PYTHON_BIN") ./scripts/scan_project.py --analyzer-url http://${HOST}:${PORT} --project-name $(shell_quote "$PROJECT_NAME")"
  if [[ -n "$SOURCE_ROOT" ]]; then
    SCAN_CMD+=" --source-root $(shell_quote "$SOURCE_ROOT")"
  fi
  if ! bash -lc "$SCAN_CMD" >/dev/null 2>&1; then
    echo "Smoke path failed to prepare schema via scan_project.py" >&2
    capture_window "$ANALYZER_PANE_TARGET" -80 >&2 || true
    exit 17
  fi
fi
if [[ -z "$MODULE_PROBE" ]]; then
  MODULE_PROBE="$(curl -fsS "http://${HOST}:${PORT}/schema/${PROJECT_NAME}" | python3 -c 'import json,sys; data=json.load(sys.stdin); modules=data.get("modules") or []; print((modules[0] or {}).get("module_path","") if modules else "")')"
fi
if [[ -z "$MODULE_PROBE" ]]; then
  echo "Could not determine a module probe from analyzer schema" >&2
  exit 18
fi
TUI_INNER_CMD="cd $(shell_quote "$ROOT_DIR") && export INTROSPECTOR_ANALYZER_URL=http://${HOST}:${PORT} && export INTROSPECTOR_PROJECT_NAME=$(shell_quote "$PROJECT_NAME") && export INTROSPECTOR_TUI_INITIAL_MODULE=$(shell_quote "$MODULE_PROBE")"
if [[ -n "$SOURCE_ROOT" ]]; then
  TUI_INNER_CMD+=" && export INTROSPECTOR_SOURCE_ROOT=$(shell_quote "$SOURCE_ROOT")"
fi
TUI_INNER_CMD+=" && $(shell_quote "$PYTHON_BIN") -m project_introspector.tui_app"
TUI_CMD="bash -lc $(shell_quote "$TUI_INNER_CMD; status=\$?; printf '\n[TUI_EXIT %s]\n' \"\$status\"; sleep 15; exit \$status")"
TUI_META="$(tmux new-window -d -P -F '#{window_id} #{pane_id}' -t "$SESSION:" -n "$TUI_WINDOW_NAME" "$TUI_CMD")"
TUI_WINDOW_TARGET="${TUI_META%% *}"
TUI_PANE_TARGET="${TUI_META##* }"
if ! wait_for_tui_capture "$TUI_PANE_TARGET"; then
  echo "TUI window did not reach ready state before capture" >&2
  capture_window "$TUI_PANE_TARGET" -120 >&2 || true
  exit 11
fi

TUI_PANE_META="$(tmux display-message -p -t "$TUI_PANE_TARGET" '#{pane_dead} #{pane_current_command} #{pane_width}x#{pane_height}')"
TUI_BOOT_CAPTURE="$(capture_tui_pane "$TUI_PANE_TARGET" -120)"

ANALYZER_CAPTURE=""
if [[ -n "${ANALYZER_PANE_TARGET:-}" ]]; then
  ANALYZER_CAPTURE="$(capture_window "$ANALYZER_PANE_TARGET" -120)"
fi
TUI_CAPTURE_PLAIN="$(tmux capture-pane -p -t "$TUI_PANE_TARGET" -S -120)"
TUI_CAPTURE="$(capture_tui_pane "$TUI_PANE_TARGET" -120)"

if grep -Eq 'Traceback|Textual is not installed|ModuleNotFoundError|No module named|\[TUI_EXIT ' <<<"$TUI_CAPTURE"; then
  echo "TUI pane shows traceback or missing dependency" >&2
  printf '%s\n' "$TUI_CAPTURE" >&2
  exit 12
fi

if ! grep -q "module_path:" <<<"$TUI_CAPTURE_PLAIN"; then
  echo "TUI pane did not show the probed baseline module" >&2
  printf '%s\n' "$TUI_CAPTURE" >&2
  exit 13
fi

if ! grep -Eq 'source_path:|enrichment:' <<<"$TUI_CAPTURE_PLAIN"; then
  echo "TUI explorer did not render baseline module detail fields" >&2
  printf '%s\n' "$TUI_CAPTURE" >&2
  exit 14
fi

if [[ "$MODE" != "live" ]] && ! grep -q 'GET /llm/status HTTP/1.1" 200 OK' <<<"$ANALYZER_CAPTURE"; then
  echo "Analyzer pane did not log /llm/status access" >&2
  printf '%s\n' "$ANALYZER_CAPTURE" >&2
  exit 15
fi

printf 'TMUX_SMOKE_OK\n'
printf 'SESSION=%s\n' "$SESSION"
printf 'MODE=%s\n' "$MODE"
printf 'ANALYZER_WINDOW=%s\n' "$ANALYZER_WINDOW_NAME"
printf 'TUI_WINDOW=%s\n' "$TUI_WINDOW_NAME"
printf 'STATUS_JSON=%s\n' "$STATUS_JSON"
printf 'TUI_PANE_META=%s\n' "$TUI_PANE_META"
printf 'SOURCE_ROOT=%s\n' "${SOURCE_ROOT:-<default>}"
printf 'PROJECT_NAME=%s\n' "$PROJECT_NAME"
printf 'ANALYZER_CAPTURE_BEGIN\n%s\nANALYZER_CAPTURE_END\n' "$ANALYZER_CAPTURE"
printf 'TUI_CAPTURE_BEGIN\n%s\nTUI_CAPTURE_END\n' "$TUI_CAPTURE"
