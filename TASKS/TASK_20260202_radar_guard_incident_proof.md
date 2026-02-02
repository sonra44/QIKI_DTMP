# TASK: Radar guard → event → ORION incident → ack/clear proof (Phase1, no-mocks)

**Date:** 2026-02-02  
**Goal:** Prove the operator loop for radar guard alerts: guard rule violation → event → ORION incident → operator `ack` + `clear` → operator-action audit events.  

## Canonical sources

- Guard rules: `src/qiki/resources/radar/guard_rules.yaml`
- Incident rules: `config/incident_rules.yaml`

This proof focuses on guard rule `UNKNOWN_CONTACT_CLOSE` (unknown contact in close range).

## Changes

1) Guard alert events publisher (FastStream bridge)

- `src/qiki/services/faststream_bridge/app.py` evaluates guard rules on the published radar track and emits a guard alert event on a per-key cadence.
- `src/qiki/services/faststream_bridge/radar_guard_publisher.py` publishes the event to NATS with CloudEvent headers.
- Subject: `qiki.events.v1.radar.guard` (`RADAR_GUARD_ALERTS`)
- Opt-in flag: `RADAR_GUARD_EVENTS_ENABLED=1` (default off to avoid surprise incidents).
- Cadence: `RADAR_GUARD_PUBLISH_INTERVAL_S` (default `2.0`) to avoid missing alerts due to subscription timing.

2) Incident rule for guard alert

- `config/incident_rules.yaml` includes `UNKNOWN_CONTACT_CLOSE` rule:
  - match: type=`radar`, source=`guard`, subject=`UNKNOWN_CONTACT_CLOSE`, field=`range_m`, threshold `< 70`.

3) Integration test proof

- `tests/integration/test_radar_guard_events.py`
  - waits for `UNKNOWN_CONTACT_CLOSE` guard alert event when `RADAR_GUARD_EVENTS_ENABLED=1`.

## How to run (Docker-first)

1) Start Phase1 + ORION with guard events enabled:

- `RADAR_GUARD_EVENTS_ENABLED=1 RADAR_SR_THRESHOLD_M=100 docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build`

2) Run integration proof:

- `./scripts/run_integration_tests_docker.sh tests/integration/test_radar_guard_events.py`

3) ORION proof (tmux/attach):

Expected incident key (deterministic):

- `UNKNOWN_CONTACT_CLOSE|radar|guard|UNKNOWN_CONTACT_CLOSE|<track_id>`

Operator actions (recommended order for a complete lifecycle):

- `simulation.pause` (stops new radar frames/events so the incident stays acked)
- `ack UNKNOWN_CONTACT_CLOSE|radar|guard|UNKNOWN_CONTACT_CLOSE|<track_id>`
- `clear`

4) Audit proof (no-mocks):

Subscribe to `qiki.events.v1.operator.actions` and verify:

- `kind=incident_ack` with `rule_id=UNKNOWN_CONTACT_CLOSE`
- `kind=incident_clear` with `cleared_count>=1`

## Evidence (2026-02-02)

- Integration: `tests/integration/test_radar_guard_events.py` → `1 passed`
- ORION loop (tmux pane `%20`):
  - `simulation.pause` (ACK applied)
  - `ack UNKNOWN_CONTACT_CLOSE|radar|guard|UNKNOWN_CONTACT_CLOSE|acadd171-247d-4e09-8106-3b311e9d5fed`
  - `clear` → cleared count `1`
- Operator actions (JetStream `QIKI_EVENTS_V1`, subject `qiki.events.v1.operator.actions`):
  - `kind=incident_ack` with `incident_key=UNKNOWN_CONTACT_CLOSE|...|acadd171-...`
  - `kind=incident_clear` with `cleared_incidents[]` containing the same key
