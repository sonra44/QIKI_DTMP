# TASK: Control ACK envelope proof (Phase1, no-mocks)

**Date:** 2026-02-02  
**Goal:** Prove `qiki.responses.control` ACK is backward-compatible and complete (version/kind/timestamp + aliases).

## Canonical sources

- Control subject: `src/qiki/shared/nats_subjects.py` → `RESPONSES_CONTROL`
- Producer: `src/qiki/services/q_sim_service/grpc_server.py` → `_build_control_response_payload()`
- Consumer: `src/qiki/services/operator_console/main_orion.py` → `handle_control_response()`

## ACK contract (as emitted today)

Required fields:

- `version=1`
- `kind` (echo of command name)
- `success` and alias `ok` (same boolean)
- `requestId` and alias `request_id` (same id)
- `timestamp` (ISO string)
- `payload` (dict: `command_name`, `status`)

Error (when `ok=false`):

- legacy error code string: `error`
- structured error object: `error_detail={code,message,details}`

## Integration proof

- `tests/integration/test_control_ack_envelope.py`
  - sends `sim.start`
  - asserts ACK contains the required envelope fields and aliases

## How to run (Docker-first)

1) Start Phase1 stack (any bot config):

- `docker compose -f docker-compose.phase1.yml up -d --build`

2) Run integration proof:

- `./scripts/run_integration_tests_docker.sh tests/integration/test_control_ack_envelope.py`

## Evidence (2026-02-02)

- `./scripts/run_integration_tests_docker.sh tests/integration/test_control_ack_envelope.py` → pass
- `QUALITY_GATE_PROFILE=full bash scripts/quality_gate_docker.sh` → OK

