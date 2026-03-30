#!/usr/bin/env bash
set -euo pipefail

# Canonical minimal regression entry for the current post-closure
# resumed-observation slice on the Phase1/operator stack.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

PHASE1_COMPOSE="$PROJECT_ROOT/docker-compose.phase1.yml"
OPERATOR_COMPOSE="$PROJECT_ROOT/docker-compose.operator.yml"
STACK=(-f "$PHASE1_COMPOSE" -f "$OPERATOR_COMPOSE")
PHASE1_ONLY=(-f "$PHASE1_COMPOSE")
LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/qiki-minimal-regression-pack.XXXXXX")"

UNIT_STEP="targeted unit regression pack"
RESUMED_STEP="canonical resumed observation smoke"
BIOS_STEP="BIOS live support-tier smoke"

UNIT_CMD=(
  docker compose "${PHASE1_ONLY[@]}" exec -T qiki-dev pytest -q
  tests/unit/test_orion_v_qiki_loop.py::test_resumed_safe_observation_records_signature_changed_result_on_same_objective
  tests/unit/test_orion_v_qiki_loop.py::test_live_observation_track_snapshot_logs_public_identity_without_format_noise
  tests/unit/test_qiki_orion_intents_service.py::test_find_resumable_observation_objective_logs_qcore_and_public_identity
  tests/unit/test_orion_v_procedure_engine.py
  src/qiki/services/q_bios_service/tests/test_service_contract.py
  src/qiki/services/registrar/tests/test_main_contract.py
)

RESUMED_CMD=(
  docker compose "${PHASE1_ONLY[@]}" exec -T qiki-dev bash -lc
  "ORIONV_PROCEDURES_DIR=/workspace/config/orion_v/procedures QIKI_OBSERVATION_STYLE=slow QIKI_RESUME_XPDR_MODE=SPOOF python tools/orion_v_qiki_observation_objective_seed_smoke.py"
)

BIOS_CMD=(
  docker compose "${PHASE1_ONLY[@]}" exec -T qiki-dev bash -lc
  "NATS_URL=nats://nats:4222 python tools/bios_status_smoke.py"
)

STEP_RESULTS=()
CURRENT_STEP=""

usage() {
  cat <<'EOF'
Usage: scripts/run_minimal_regression_pack.sh

Runs the canonical minimal regression entry for the current
post-closure resumed-observation slice:
  1. Targeted unit regression pack
  2. Canonical resumed observation smoke
  3. BIOS live support-tier smoke

This is not the full validation or broad acceptance suite.
Failure severity interpretation for this pack is documented in:
  TASK_OUT/regression_failure_severity_map.md

Assumptions:
  - canonical stack is the live Phase1/operator contour from:
      docker-compose.phase1.yml + docker-compose.operator.yml
  - expected running services:
      nats qiki-dev q-sim-service q-core-intents faststream-bridge q-bios-service operator-console
  - ORION procedures are loaded from:
      /workspace/config/orion_v/procedures
  - BIOS smoke runs inside qiki-dev with:
      NATS_URL=nats://nats:4222

Artifacts:
  - full per-step logs are written to a temp directory printed at startup
EOF
}

cleanup_on_exit() {
  local exit_code="$1"
  if [[ "$exit_code" -ne 0 && -n "$CURRENT_STEP" ]]; then
    printf '\n[pack] aborted during: %s\n' "$CURRENT_STEP" >&2
  fi
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf '[pack] missing required command: %s\n' "$command_name" >&2
    exit 1
  fi
}

print_step_header() {
  local step_name="$1"
  printf '\n[pack] %s\n' "$step_name"
}

print_step_interpretation() {
  local step_name="$1"
  case "$step_name" in
    "$UNIT_STEP")
      cat <<'EOF'
[pack] operational interpretation:
  - maintenance-level by default
  - blocker-candidate only if the failure breaks the resumed same-contour
    closeout baseline (`signature_changed` / procedure-loading on this slice)
EOF
      ;;
    "$RESUMED_STEP")
      cat <<'EOF'
[pack] operational interpretation:
  - blocker-candidate for the current slice
  - treat as P0 only if it falsifies the already-closed canonical resumed
    observation / `signature_changed` path
EOF
      ;;
    "$BIOS_STEP")
      cat <<'EOF'
[pack] operational interpretation:
  - maintenance-level by default
  - warning/non-blocking only for extra diagnostic noise outside required
    proof markers
EOF
      ;;
  esac
}

print_markers() {
  local step_name="$1"
  case "$step_name" in
    "$RESUMED_STEP")
      cat <<'EOF'
[pack] required proof markers:
  - INITIAL_TARGET_SOURCE=orion_live_radar_cache
  - RESUME_ACTION=resume_observation
  - CONTINUATION_RESULT=signature_changed
  - FINAL_QIKI_STATUS=confirmed
EOF
      ;;
    "$BIOS_STEP")
      cat <<'EOF'
[pack] required proof markers:
  - OK: received bios status on qiki.events.v1.bios_status
  - payload contract checks include source/subject/version/timestamp/bios_version/firmware_version/post_results
EOF
      ;;
  esac
}

assert_running_stack() {
  local expected_services=(
    nats
    qiki-dev
    q-sim-service
    q-core-intents
    faststream-bridge
    q-bios-service
    operator-console
  )
  local running services_output service

  mapfile -t running < <(docker compose "${STACK[@]}" ps --services --status running)
  services_output="$(printf '%s\n' "${running[@]}")"

  printf '[pack] canonical stack assumptions\n'
  printf '  compose: docker-compose.phase1.yml + docker-compose.operator.yml\n'
  printf '  procedures: /workspace/config/orion_v/procedures\n'
  printf '  bios smoke NATS_URL: nats://nats:4222\n'
  printf '  logs: %s\n' "$LOG_DIR"
  printf '\n[pack] live stack status\n'
  docker compose "${STACK[@]}" ps "${expected_services[@]}"

  for service in "${expected_services[@]}"; do
    if ! grep -qx "$service" <<<"$services_output"; then
      printf '\n[pack] preflight failed: required service is not running: %s\n' "$service" >&2
      exit 1
    fi
  done
}

run_step() {
  local step_name="$1"
  local log_path="$2"
  shift 2
  local -a command=("$@")

  CURRENT_STEP="$step_name"
  print_step_header "$step_name"
  print_step_interpretation "$step_name"
  print_markers "$step_name"
  printf '[pack] command:'
  printf ' %q' "${command[@]}"
  printf '\n'

  if "${command[@]}" 2>&1 | tee "$log_path"; then
    STEP_RESULTS+=("PASS | $step_name | $log_path")
  else
    STEP_RESULTS+=("FAIL | $step_name | $log_path")
    printf '\n[pack] failed step: %s\n' "$step_name" >&2
    print_step_interpretation "$step_name" >&2
    printf '[pack] saved log: %s\n' "$log_path" >&2
    printf '[pack] last log lines:\n' >&2
    tail -n 40 "$log_path" >&2 || true
    exit 1
  fi

  CURRENT_STEP=""
}

assert_log_contains() {
  local log_path="$1"
  local marker="$2"
  local step_name="$3"
  if ! grep -Fq "$marker" "$log_path"; then
    printf '\n[pack] %s missing required proof marker: %s\n' "$step_name" "$marker" >&2
    print_step_interpretation "$step_name" >&2
    printf '[pack] saved log: %s\n' "$log_path" >&2
    exit 1
  fi
}

print_summary() {
  local line
  printf '\n[pack] summary\n'
  for line in "${STEP_RESULTS[@]}"; do
    printf '  %s\n' "$line"
  done
  printf '\n[pack] minimal regression pack passed\n'
}

main() {
  trap 'cleanup_on_exit $?' EXIT

  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
  fi

  cd "$PROJECT_ROOT"
  require_command docker

  assert_running_stack

  local unit_log="$LOG_DIR/unit_regression.log"
  local resumed_log="$LOG_DIR/resumed_observation_smoke.log"
  local bios_log="$LOG_DIR/bios_support_tier_smoke.log"

  run_step "$UNIT_STEP" "$unit_log" "${UNIT_CMD[@]}"
  run_step "$RESUMED_STEP" "$resumed_log" "${RESUMED_CMD[@]}"
  assert_log_contains "$resumed_log" "INITIAL_TARGET_SOURCE=orion_live_radar_cache" "$RESUMED_STEP"
  assert_log_contains "$resumed_log" "RESUME_ACTION=resume_observation" "$RESUMED_STEP"
  assert_log_contains "$resumed_log" "CONTINUATION_RESULT=signature_changed" "$RESUMED_STEP"
  assert_log_contains "$resumed_log" "FINAL_QIKI_STATUS=confirmed" "$RESUMED_STEP"

  run_step "$BIOS_STEP" "$bios_log" "${BIOS_CMD[@]}"
  assert_log_contains "$bios_log" "OK: received bios status on qiki.events.v1.bios_status" "$BIOS_STEP"

  print_summary
}

main "$@"
