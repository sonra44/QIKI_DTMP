# TASK: ORION control/events provenance marker (TRUSTED/UNTRUSTED)

Date: 2026-02-06
Owner: Codex

## Why
Control-plane responses and event subjects can be spoofed on an unauthenticated bus. Operator UI needs a lightweight trust hint without protocol redesign.

## Scope
- Add deterministic provenance marker in ORION for:
  - Events screen (`Trust` column + Inspector field)
  - Control response console log lines
- Keep behavior non-blocking and no-mocks.

## Changes
- `src/qiki/services/operator_console/main_orion.py`
  - Added `_provenance_marker(channel, subject)`:
    - `events`: `TRUSTED` if subject starts with `qiki.events.v1.` else `UNTRUSTED`
    - `control_response`: `TRUSTED` if subject equals `qiki.responses.control` else `UNTRUSTED`
  - Events table now includes `Trust/Доверие` column.
  - Events inspector now shows trust marker for selected incident.
  - Control response log now includes marker: `...[TRUSTED|UNTRUSTED]: ...`.
  - Updated responsive column widths and seed rows for the new Events column count.

- `tests/unit/test_orion_control_provenance.py`
  - Added unit tests for marker classification.
  - Added unit test proving control-response log contains trusted/untrusted marker.
  - Added unit test proving Events table row includes trust column value.

## Verification
- Targeted unit tests:
  - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_control_provenance.py tests/unit/test_orion_events_seed_row_message.py`
  - Result: `4 passed`

- Full quality gate:
  - `bash scripts/quality_gate_docker.sh`
  - Result: `[quality-gate] OK`

## Outcome
A lightweight, deterministic provenance signal is now visible to operators on both incoming events and control responses, reducing spoofing/deception risk with minimal UX/code impact.
