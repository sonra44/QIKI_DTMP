# TASK: Power SoC dynamics proof (Phase1, no-mocks)

**Date:** 2026-02-02  
**Goal:** Prove that `power.soc_pct` changes deterministically while RUNNING (sim truth), and freezes while PAUSED/STOPPED — using only real telemetry.

## Canonical sources

- Power Plane implementation: `src/qiki/services/q_sim_service/core/world_model.py`
- Telemetry key: `qiki.telemetry` → `power.soc_pct` (see payload builder in `world_model.get_state()`)

## Fixture

- `tests/fixtures/bot_config_power_soc_drain.json`
  - deterministic net deficit: `base_power_in_w=0`, `base_power_out_w=72W`, `power_capacity_wh=10Wh`
  - expected SoC drop rate: ~`0.2%/s` (so it changes measurably in a few seconds, but does not hit SoC shedding thresholds during a typical integration run)

## Integration proof

- `tests/integration/test_power_soc_dynamics.py`
  - sends `sim.start`, then samples `power.soc_pct` for ~3s and asserts it decreases
  - sends `sim.pause`, then samples for ~2s and asserts SoC is stable
  - sends `sim.stop`, then samples for ~2s and asserts SoC is stable

## How to run (Docker-first)

1) Start Phase1 + ORION with the SoC drain fixture:

- `BOT_CONFIG_PATH=/workspace/tests/fixtures/bot_config_power_soc_drain.json docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build`

2) Run integration proof:

- `./scripts/run_integration_tests_docker.sh tests/integration/test_power_soc_dynamics.py`

## Evidence (2026-02-02)

- `./scripts/run_integration_tests_docker.sh tests/integration/test_power_soc_dynamics.py` → pass
- `QUALITY_GATE_PROFILE=full bash scripts/quality_gate_docker.sh` → OK

