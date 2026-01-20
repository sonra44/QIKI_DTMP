#!/usr/bin/env bash
set -euo pipefail

compose_files=(-f docker-compose.phase1.yml)

if [[ "${QIKI_USE_OPERATOR_COMPOSE:-0}" == "1" ]]; then
  compose_files+=(-f docker-compose.operator.yml)
fi

dc() {
  docker compose "${compose_files[@]}" "$@"
}

echo "[quality-gate] Services status (informational)"
dc ps

SCOPE="${QUALITY_GATE_SCOPE:-.}"

echo "[quality-gate] Ruff (lint)"
dc exec -T qiki-dev ruff check ${SCOPE}

echo "[quality-gate] Ruff (format check)"
dc exec -T qiki-dev ruff format --check ${SCOPE}

echo "[quality-gate] Pytest"
dc exec -T qiki-dev pytest -q ${QUALITY_GATE_PYTEST_PATHS:-}

echo "[quality-gate] Mypy"
dc exec -T qiki-dev mypy --config-file mypy.ini ${QUALITY_GATE_MYPY_PATHS:-src}

echo "[quality-gate] OK"
