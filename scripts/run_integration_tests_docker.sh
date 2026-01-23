#!/usr/bin/env bash
set -euo pipefail

compose_files=(-f docker-compose.phase1.yml)

if [[ "${QIKI_USE_OPERATOR_COMPOSE:-0}" == "1" ]]; then
  compose_files+=(-f docker-compose.operator.yml)
fi

dc() {
  docker compose "${compose_files[@]}" "$@"
}

# IMPORTANT: pytest.ini has `addopts = -q -m "not integration"`.
# To run integration-marked tests, we must override addopts.

paths=("$@")
if ((${#paths[@]} == 0)); then
  paths=(tests/integration)
fi

dc exec -T qiki-dev env NATS_URL="${NATS_URL:-nats://nats:4222}" \
  pytest -o addopts='' -m integration -q "${paths[@]}"
