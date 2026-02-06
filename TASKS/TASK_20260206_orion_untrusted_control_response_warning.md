# TASK: ORION control-response trust marker severity hardening

Date: 2026-02-06
Owner: Codex

## Why
`UNTRUSTED` control responses were visible in text but logged at `info`, which can hide spoofing/deception signals in operator workflows.

## Scope
- Keep existing provenance marker logic.
- Escalate log level for untrusted control responses to `warning`.
- Prove behavior by unit tests and quality gate.

## Changes
- `src/qiki/services/operator_console/main_orion.py`
  - In `handle_control_response`, map level by marker:
    - `TRUSTED -> info`
    - `UNTRUSTED -> warning`
  - Keep marker text unchanged: `Control response[TRUSTED|UNTRUSTED]: ...`.

- `tests/unit/test_orion_control_provenance.py`
  - Updated test to capture `(message, level)` and assert:
    - trusted response logs with `info`
    - untrusted response logs with `warning`

## Verification
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_control_provenance.py` -> `3 passed`
- `bash scripts/quality_gate_docker.sh` -> `[quality-gate] OK`

## Outcome
Untrusted control-plane responses are now fail-loud in operator logs without protocol changes.
