# TASK: Thermal incident ack/clear proof (Phase1, no-mocks)

**Date:** 2026-02-02  
**Goal:** Prove the operator loop for thermal incidents: sim event → ORION incident → operator `ack` → operator `clear` → operator-action audit events.  

## Canonical rules

Thermal incident rule is defined in:

- `config/incident_rules.yaml` → `TEMP_CORE_SPIKE` (sensor/thermal/core, field `temp`, threshold `>70`, `min_duration_s=3`)

## Changes / fixtures

- `tests/fixtures/bot_config_temp_core_spike.json`:
  - thermal core starts at `80°C` and remains stable (cooling and ambient exchange are zero) so the incident is deterministic.
- `tests/integration/test_thermal_core_spike_event.py`:
  - subscribes to `qiki.events.v1.sensor.thermal` and proves `temp > 70` samples are published (no-mocks).

## How to run (Docker-first)

1) Start/restart Phase1 stack with the thermal-spike bot config:

- `BOT_CONFIG_PATH=/workspace/tests/fixtures/bot_config_temp_core_spike.json docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build`

2) Run proof integration test:

- `./scripts/run_integration_tests_docker.sh tests/integration/test_thermal_core_spike_event.py`

3) ORION operator actions proof (tmux/attach):

Wait ~4 seconds (min_duration_s=3) for `TEMP_CORE_SPIKE|sensor|thermal|core` to appear, then run:

- `ack TEMP_CORE_SPIKE|sensor|thermal|core`
- `clear`

Expected ORION output:

- `Acknowledged/Подтверждено: TEMP_CORE_SPIKE|sensor|thermal|core`
- `Cleared acknowledged incidents/Очищено подтвержденных инцидентов: 1`

4) Audit events proof (no-mocks)

Subscribe to `qiki.events.v1.operator.actions` and verify:

- `kind=incident_ack` with `rule_id=TEMP_CORE_SPIKE`
- `kind=incident_clear` with `cleared_count=1`

Observed (example payloads):

- `incident_ack`:
  - `{"category":"audit","kind":"incident_ack","incident_key":"TEMP_CORE_SPIKE|sensor|thermal|core","rule_id":"TEMP_CORE_SPIKE"}`
- `incident_clear`:
  - `{"category":"audit","kind":"incident_clear","cleared_count":1,"cleared_incidents":[{"incident_id":"TEMP_CORE_SPIKE|sensor|thermal|core"}]}`
