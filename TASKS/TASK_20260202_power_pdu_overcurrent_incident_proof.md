# TASK: PDU overcurrent → event → ORION incident → ack/clear proof (Phase1, no-mocks)

**Date:** 2026-02-02  
**Goal:** Prove the operator loop for a Power Plane PDU overcurrent condition: sim event → ORION incident → operator `ack` + `clear` → operator-action events.

## Canonical sources

- Incident rules: `config/incident_rules.yaml` → `POWER_PDU_OVERCURRENT`
- PDU event subject: `src/qiki/shared/nats_subjects.py` (`SIM_POWER_PDU`)

## Changes

1) q_sim_service publishes PDU power events

- `src/qiki/services/q_sim_service/service.py`
  - publishes periodic PDU status events to `qiki.events.v1.power.pdu`
  - payload includes `overcurrent` derived from `PDU_OVERCURRENT` fault

Payload (minimal, no-mocks):

- `schema_version=1`
- `category=power`
- `source=pdu`
- `subject=main`
- `overcurrent=0|1`
- `pdu_limit_w`, `power_out_w`, `bus_a`, `bus_v`
- `ts_epoch`

2) Incident rule

- `config/incident_rules.yaml` includes `POWER_PDU_OVERCURRENT`:
  - match: type=`power`, source=`pdu`, subject=`main`, field=`overcurrent`, threshold `= 1`
  - `require_ack=true`, `auto_clear=false`

3) Fixture + integration proof

- Fixture: `tests/fixtures/bot_config_power_pdu_overcurrent.json` (low `max_bus_a` forces overcurrent)
- Integration: `tests/integration/test_power_pdu_overcurrent_event.py`
  - subscribes to `qiki.events.v1.power.pdu`
  - asserts an `overcurrent=1` sample appears (skips when fixture is not running)

## How to run (Docker-first)

1) Start Phase1 + ORION with the PDU overcurrent fixture:

- `BOT_CONFIG_PATH=/workspace/tests/fixtures/bot_config_power_pdu_overcurrent.json docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build`

2) Run integration proof:

- `./scripts/run_integration_tests_docker.sh tests/integration/test_power_pdu_overcurrent_event.py`

3) ORION proof (tmux/attach)

Expected incident key:

- `POWER_PDU_OVERCURRENT|power|pdu|main`

Operator actions:

- `ack POWER_PDU_OVERCURRENT|power|pdu|main`
- `clear`

4) Audit proof (no-mocks)

Fetch from JetStream `QIKI_EVENTS_V1`, subject `qiki.events.v1.operator.actions` and verify:

- `kind=incident_ack` with `incident_key=POWER_PDU_OVERCURRENT|power|pdu|main`
- `kind=incident_clear` with `cleared_incidents[]` containing the same key

## Evidence (2026-02-02)

- Stack start (fixture): `BOT_CONFIG_PATH=/workspace/tests/fixtures/bot_config_power_pdu_overcurrent.json docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build`
- Integration: `./scripts/run_integration_tests_docker.sh tests/integration/test_power_pdu_overcurrent_event.py` → pass
- ORION: `ack POWER_PDU_OVERCURRENT|power|pdu|main` then `clear` → cleared=1
- Operator-action events (JetStream `QIKI_EVENTS_V1`, subject `qiki.events.v1.operator.actions`):
  - `{"category":"audit","kind":"incident_ack","incident_key":"POWER_PDU_OVERCURRENT|power|pdu|main","rule_id":"POWER_PDU_OVERCURRENT","severity":"A"}`
  - `{"category":"audit","kind":"incident_clear","cleared_count":1,"cleared_incidents":[{"incident_id":"POWER_PDU_OVERCURRENT|power|pdu|main","rule_id":"POWER_PDU_OVERCURRENT"}]}`
- Gate: `QUALITY_GATE_PROFILE=full bash scripts/quality_gate_docker.sh` → OK

