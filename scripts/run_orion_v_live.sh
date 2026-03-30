#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILES=(-f docker-compose.phase1.yml -f docker-compose.operator.yml)
CONTAINER_NAME="${ORION_V_CONTAINER_NAME:-}"
ENTRYPOINT_CMD=(python main_orion_v.py)

resolve_container_name() {
  if [[ -n "$CONTAINER_NAME" ]]; then
    printf '%s\n' "$CONTAINER_NAME"
    return 0
  fi

  local detected=""
  detected="$(docker ps \
    --filter 'label=com.docker.compose.service=operator-console' \
    --format '{{.Names}}' \
    | head -n 1)"
  if [[ -n "$detected" ]]; then
    printf '%s\n' "$detected"
    return 0
  fi

  if docker inspect qiki-operator-console >/dev/null 2>&1; then
    printf '%s\n' "qiki-operator-console"
    return 0
  fi

  return 1
}

compose_exec_orion() {
  docker compose "${COMPOSE_FILES[@]}" exec operator-console "${ENTRYPOINT_CMD[@]}"
}

usage() {
  cat <<'EOF'
Usage: scripts/run_orion_v_live.sh

Starts a fresh interactive ORION V TTY inside the running operator-console service.

Environment:
  ORION_V_CONTAINER_NAME   Optional fallback container name for direct `docker exec`
                           if compose service lookup is unavailable.

Notes:
  - canonical live path under tmux
  - avoids degraded fullscreen behavior seen with `docker attach`
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

cd "$PROJECT_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed or not in PATH." >&2
  exit 1
fi

if docker compose "${COMPOSE_FILES[@]}" ps -q operator-console >/dev/null 2>&1; then
  if [[ -n "$(docker compose "${COMPOSE_FILES[@]}" ps -q operator-console)" ]]; then
    compose_exec_orion
    exit $?
  fi
fi

if ! CONTAINER_NAME="$(resolve_container_name)"; then
  cat >&2 <<EOF
Error: operator-console container was not found.
Start ORION V first:
  docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console

If compose metadata is unavailable and the container uses a non-standard name, rerun with:
  ORION_V_CONTAINER_NAME=<actual-container-name> scripts/run_orion_v_live.sh
EOF
  exit 1
fi

if ! docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  cat >&2 <<EOF
Error: container '$CONTAINER_NAME' was not found.
Start ORION V first:
  docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console
EOF
  exit 1
fi

if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")" != "true" ]]; then
  cat >&2 <<EOF
Error: container '$CONTAINER_NAME' is not running.
Start ORION V first:
  docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console
EOF
  exit 1
fi

exec docker exec -it "$CONTAINER_NAME" "${ENTRYPOINT_CMD[@]}"
