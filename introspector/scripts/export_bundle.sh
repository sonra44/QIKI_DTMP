#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-}"
OUTPUT_PATH="${2:-}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

usage() {
  cat >&2 <<'EOF'
Usage:
  scripts/export_bundle.sh source-baseline [output.zip]
  scripts/export_bundle.sh evidence-bundle [output.zip]

Modes:
  source-baseline  Package commit/handoff-ready source only.
  evidence-bundle  Package generated analyzer storage and live proof artifacts.
EOF
  exit 64
}

if [[ -z "$MODE" ]]; then
  usage
fi

cd "$ROOT_DIR/.."

case "$MODE" in
  source-baseline)
    OUTPUT_PATH="${OUTPUT_PATH:-$PWD/introspector_source_baseline_${TIMESTAMP}.zip}"
    zip -qr "$OUTPUT_PATH" introspector \
      -x 'introspector/.venv/*' \
      -x 'introspector/**/__pycache__/*' \
      -x 'introspector/.pytest_cache/*' \
      -x 'introspector/.mypy_cache/*' \
      -x 'introspector/.ruff_cache/*' \
      -x 'introspector/.serena/*' \
      -x 'introspector/analyzer/data/*' \
      -x 'introspector/analyzer/data/static/*' \
      -x 'introspector/analyzer/data/runtime/*' \
      -x 'introspector/analyzer/data/derived/*' \
      -x 'introspector/tmp/live_module_pass/*'
    ;;
  evidence-bundle)
    OUTPUT_PATH="${OUTPUT_PATH:-$PWD/introspector_evidence_bundle_${TIMESTAMP}.zip}"
    zip -qr "$OUTPUT_PATH" \
      introspector/README.md \
      introspector/BASELINE.md \
      introspector/scripts/run_fresh_analyzer.sh \
      introspector/scripts/live_module_pass.py \
      introspector/scripts/clean_dev_artifacts.sh \
      introspector/analyzer/data \
      introspector/tmp/live_module_pass
    ;;
  *)
    usage
    ;;
esac

echo "$OUTPUT_PATH"
