# TASK: Power SoT alignment — bot_config battery capacity + init SoC

**Date:** 2026-02-02  
**Scope:** Phase1 / Power Plane SoT alignment (no-mocks)  

## Problem

Power/EPS behavior in Phase1 must be fully explained by the runtime hardware profile (no-mocks). Two fields are treated as canonical Power SoT:

- `hardware_profile.power_capacity_wh`
- `hardware_profile.battery_soc_init_pct`

These must remain present and valid as the code evolves (otherwise simulation can emit power faults and operator telemetry becomes non-evidenced).

## Change

- Adjusted default `hardware_profile.battery_soc_init_pct` to `80.0` (start not fully charged; makes Power UI and load-shedding behavior observable earlier).
- Added a unit test that asserts the canonical fields exist and are in valid ranges.

Files:

- `src/qiki/services/q_core_agent/config/bot_config.json`
- `tests/unit/test_bot_config_power_sot.py`

## Evidence

Unit test (Docker-first):

- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_bot_config_power_sot.py`

Telemetry sample (no faults; SoC present):

- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY' ... PY`

Observed payload excerpt:

```json
{
  "soc_pct": 80.01786848974949,
  "faults": []
}
```
