# TASK: Thermal trip → event → ORION incident → ack/clear proof (Phase1, no-mocks)

**Date:** 2026-02-02  
**Goal:** Prove the operator loop for a thermal TRIP (edge event): trip → event → ORION incident → operator `ack` + `clear` → operator-action events.  

## Canonical sources

- Incident rules: `config/incident_rules.yaml`
- Thermal trip event subject: `src/qiki/shared/nats_subjects.py` (`SIM_SENSOR_THERMAL_TRIP`)

## Changes

1) q_sim_service publishes thermal trip edge events

- `src/qiki/services/q_sim_service/service.py`
  - continues publishing periodic thermal readings to `qiki.events.v1.sensor.thermal` (used by `TEMP_CORE_SPIKE`)
  - adds edge events to `qiki.events.v1.sensor.thermal.trip` when thermal trip state for `core` changes

Payload contract (no-mocks, minimal):

- `schema_version=1`
- `category=sensor`
- `kind=thermal_trip|thermal_clear`
- `source=thermal`
- `subject=core`
- `tripped=1|0`
- `temp`, `trip_c`, `hys_c`
- `ts_epoch`

2) Incident rule for thermal trip

- `config/incident_rules.yaml` includes `TEMP_CORE_TRIP` rule:
  - match: type=`sensor`, source=`thermal`, subject=`core`, field=`tripped`, threshold `= 1`
  - `require_ack=true`, `auto_clear=false`

3) Fixtures + integration proof

- Fixture: `tests/fixtures/bot_config_temp_core_trip.json` (core starts above `t_max_c`)
- Integration: `tests/integration/test_thermal_core_trip_event.py`
  - waits for `qiki.events.v1.sensor.thermal.trip` event and asserts it is a TRIP edge

## How to run (Docker-first)

1) Start Phase1 + ORION with the trip fixture:

- `BOT_CONFIG_PATH=/workspace/tests/fixtures/bot_config_temp_core_trip.json docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build`

2) Run integration proof:

- `./scripts/run_integration_tests_docker.sh tests/integration/test_thermal_core_trip_event.py`

3) ORION proof (tmux/attach):

Expected incident key:

- `TEMP_CORE_TRIP|sensor|thermal|core`

Operator actions:

- `ack TEMP_CORE_TRIP|sensor|thermal|core`
- `clear`

4) Audit proof (no-mocks):

Fetch from JetStream `QIKI_EVENTS_V1`, subject `qiki.events.v1.operator.actions` and verify:

- `kind=incident_ack` with `incident_key=TEMP_CORE_TRIP|sensor|thermal|core`
- `kind=incident_clear` with `cleared_incidents[]` containing the same key

## Evidence (2026-02-02)

- Stack start (trip fixture):
  - `BOT_CONFIG_PATH=/workspace/tests/fixtures/bot_config_temp_core_trip.json docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build`
- Because ORION subscribes to core NATS (no replay), the first edge can happen before ORION is live. To retrigger a fresh edge after ORION is running:
  - publish `sim.reset` then `sim.start` to `qiki.commands.control` (example via `docker compose ... exec -T qiki-dev python - <<'PY' ... PY`).
- ORION commands (in input):
  - `ack TEMP_CORE_TRIP|sensor|thermal|core`
  - `clear`
- Observed operator-action events (JetStream `QIKI_EVENTS_V1`, subject `qiki.events.v1.operator.actions`):
  - `{"category":"audit","kind":"incident_ack","incident_key":"TEMP_CORE_TRIP|sensor|thermal|core","rule_id":"TEMP_CORE_TRIP"}`
  - `{"category":"audit","kind":"incident_clear","cleared_count":1,"cleared_incidents":[{"incident_id":"TEMP_CORE_TRIP|sensor|thermal|core"}]}`

