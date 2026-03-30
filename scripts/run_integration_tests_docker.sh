#!/usr/bin/env bash
set -euo pipefail

compose_files=(-f docker-compose.phase1.yml)

if [[ "${QIKI_USE_OPERATOR_COMPOSE:-0}" == "1" ]]; then
  compose_files+=(-f docker-compose.operator.yml)
fi

dc() {
  docker compose "${compose_files[@]}" "$@"
}

wait_exec_ready() {
  local service="$1"
  local max_tries="${2:-60}"
  local i=0
  while ((i < max_tries)); do
    if dc exec -T "$service" true >/dev/null 2>&1; then
      return 0
    fi
    i=$((i + 1))
    sleep 1
  done
  echo "Service '$service' is not ready for exec after ${max_tries}s" >&2
  dc ps >&2 || true
  return 1
}

wait_qsim_health() {
  local max_tries="${1:-60}"
  local i=0
  while ((i < max_tries)); do
    if dc exec -T q-sim-service python - <<'PY' >/dev/null 2>&1
import grpc
from generated.q_sim_api_pb2 import HealthCheckRequest
from generated.q_sim_api_pb2_grpc import QSimAPIServiceStub
ch = grpc.insecure_channel("localhost:50051")
stub = QSimAPIServiceStub(ch)
stub.HealthCheck(HealthCheckRequest(), timeout=2.0)
PY
    then
      return 0
    fi
    i=$((i + 1))
    sleep 1
  done
  echo "Service 'q-sim-service' health check failed after ${max_tries}s" >&2
  dc ps >&2 || true
  return 1
}

# Integration tests require live sim-truth publishers (no-mocks). Make sure the
# Phase1 stack is running and rebuilt from the current workspace.
up_services=(nats nats-js-init q-sim-service faststream-bridge qiki-dev)
up_ok=0
for attempt in 1 2 3; do
  if dc up -d --build --force-recreate "${up_services[@]}" >/dev/null; then
    up_ok=1
    break
  fi
  echo "compose up failed on attempt ${attempt}/3, retrying after cleanup..." >&2
  dc down --remove-orphans >/dev/null 2>&1 || true
  sleep 2
done
if [[ "${up_ok}" -ne 1 ]]; then
  echo "Failed to prepare integration stack after retries" >&2
  dc ps >&2 || true
  exit 1
fi

wait_exec_ready qiki-dev 90
wait_qsim_health 90

# IMPORTANT: pytest.ini has `addopts = -q -m "not integration"`.
# To run integration-marked tests, we must override addopts.

paths=("$@")
if ((${#paths[@]} == 0)); then
  paths=(tests/integration)
fi

dc exec -T qiki-dev env NATS_URL="${NATS_URL:-nats://nats:4222}" \
  pytest -o addopts='' -m integration -q "${paths[@]}"
