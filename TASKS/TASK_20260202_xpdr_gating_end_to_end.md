# TASK: Comms/XPDR gating end-to-end proof (Phase1, no-mocks)

**Date:** 2026-02-02  
**Goal:** If `comms_plane.enabled=false` in runtime bot config, then `sim.xpdr.mode ON` must be rejected (ACK ok=false) and telemetry must keep XPDR forced OFF.  

## Why

XPDR mode is operator-visible and safety-relevant. It must be deterministic simulation truth based on the hardware profile, not on UI wishes or env hacks.

## Changes

1) Compose: single BOT_CONFIG_PATH override across services

- `docker-compose.phase1.yml` now sets `BOT_CONFIG_PATH` for both:
  - `q-sim-service` (simulation truth)
  - `q-bios-service` (boot/status)

This enables running Phase1 with a variant bot config without editing images.

2) q_sim_service: accept `BOT_CONFIG_PATH` (canonical) in addition to `QIKI_BOT_CONFIG_PATH` (legacy)

- `src/qiki/services/q_sim_service/service.py` loads bot config from:
  - `QIKI_BOT_CONFIG_PATH` if set (back-compat)
  - else `BOT_CONFIG_PATH` (canonical stack name)
  - else default repo path

3) Test fixture: comms disabled profile

- `tests/fixtures/bot_config_comms_disabled.json` is a runtime bot config variant with:
  - `hardware_profile.comms_plane.enabled=false`

4) Integration proof (real NATS command -> real ACK -> real telemetry)

- `tests/integration/test_xpdr_gating_flow.py`
  - When comms enabled: `sim.xpdr.mode SILENT` applies and shows in telemetry.
    - Also proves Power Plane coupling: `power.loads_w.transponder` becomes `0.0` in `SILENT`, and becomes `>0.0` again after restoring `ON` (no leaked state between tests).
  - When comms disabled: `sim.xpdr.mode ON` is rejected with `error_detail.code=comms_disabled` and telemetry stays forced `OFF`.

## How to run (Docker-first)

### A) Default run (comms enabled)

1) Start Phase1:
- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build`

2) Run only XPDR integration tests:
- `./scripts/run_integration_tests_docker.sh tests/integration/test_xpdr_gating_flow.py`

Expected: the “comms enabled” test runs, the “comms disabled” test skips.

### B) Comms-disabled run (gating proof)

1) Restart stack with a comms-disabled bot config:
- `BOT_CONFIG_PATH=/workspace/tests/fixtures/bot_config_comms_disabled.json docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build`

2) Run the same integration tests:
- `./scripts/run_integration_tests_docker.sh tests/integration/test_xpdr_gating_flow.py`

Expected: the “comms disabled” test runs and passes (ACK ok=false with `comms_disabled`), the “comms enabled” test skips.

## ORION operator evidence (tmux)

In an ORION-attached tmux pane, running:

- `xpdr.mode on`

Produces a real control response (no-mocks) indicating rejection due to hardware profile:

- `Control response/Ответ управления: success/успех=no/нет … comms disabled by hardware profile / связь отключена профилем железа`
