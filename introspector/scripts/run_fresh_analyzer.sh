#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8015}"
PYTHON_BIN="${PYTHON_BIN:-}"
REQUIRE_PROVIDER_CREDENTIALS="${REQUIRE_PROVIDER_CREDENTIALS:-0}"
ALLOW_DEGRADED_START="${ALLOW_DEGRADED_START:-0}"

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  else
    PYTHON_BIN="${PYTHON:-python3}"
  fi
fi

if [[ "$ALLOW_DEGRADED_START" == "1" ]]; then
  REQUIRE_PROVIDER_CREDENTIALS="0"
fi

provider_name="${INTROSPECTOR_PROVIDER:-${LLM_PROVIDER_NAME:-}}"
if [[ -z "$provider_name" ]]; then
  if [[ -n "${INCEPTION_API_KEY:-}" ]]; then
    provider_name="inception"
  elif [[ -n "${INTROSPECTOR_API_KEY:-${LLM_PROVIDER_API_KEY:-}}" ]]; then
    provider_name="openai-compatible"
  elif [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
    provider_name="openrouter"
  else
    provider_name="provider"
  fi
fi
provider_key="${INTROSPECTOR_API_KEY:-${LLM_PROVIDER_API_KEY:-}}"
if [[ "$provider_name" == "inception" || "$provider_name" == "mercury" || "$provider_name" == "mercury-2" ]]; then
  provider_key="${INCEPTION_API_KEY:-$provider_key}"
fi
if [[ -z "$provider_key" ]]; then
  provider_key="${OPENROUTER_API_KEY:-$provider_key}"
fi

if [[ "$REQUIRE_PROVIDER_CREDENTIALS" != "0" && -z "$provider_key" ]]; then
  cat >&2 <<EOF2
[run_fresh_analyzer] provider credentials are required for provider-backed fresh replay.
Current provider=${provider_name}
Export the matching API key before startup, or set ALLOW_DEGRADED_START=1 if you intentionally want
to start the analyzer without provider credentials and verify degraded provider-error behavior.
EOF2
  exit 2
fi

cd "$ROOT_DIR"
mkdir -p analyzer/data/static analyzer/data/runtime analyzer/data/derived tmp/live_module_pass

if [[ -n "$provider_key" ]]; then
  echo "[run_fresh_analyzer] provider credentials detected for ${provider_name}; starting analyzer on ${HOST}:${PORT}" >&2
else
  echo "[run_fresh_analyzer] starting analyzer without provider credentials; module/project LLM endpoints will stay unavailable until credentials are provided" >&2
fi

exec "$PYTHON_BIN" -m uvicorn analyzer.app:app --host "$HOST" --port "$PORT"
