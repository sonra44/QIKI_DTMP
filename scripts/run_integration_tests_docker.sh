#!/usr/bin/env bash
set -euo pipefail

compose_files=(-f docker-compose.phase1.yml)

if [[ "${QIKI_USE_OPERATOR_COMPOSE:-0}" == "1" ]]; then
  compose_files+=(-f docker-compose.operator.yml)
fi

dc() {
  docker compose "${compose_files[@]}" "$@"
}

# Integration tests require live sim-truth publishers (no-mocks). Make sure the
# Phase1 stack is running and rebuilt from the current workspace.
dc up -d --build --force-recreate nats nats-js-init q-sim-service faststream-bridge >/dev/null

# IMPORTANT: pytest.ini has `addopts = -q -m "not integration"`.
# To run integration-marked tests, we must override addopts.

paths=("$@")
if ((${#paths[@]} == 0)); then
  paths=(tests/integration)
fi

dc exec -T qiki-dev env NATS_URL="${NATS_URL:-nats://nats:4222}" \
  pytest -o addopts='' -m integration -q "${paths[@]}"
