# TASK: Active pause MVP (sim.pause/start)

Status: done
Date: 2026-01-23

## Goal

Make `simulation.pause/start/stop/reset` actually control the simulation tick loop (freeze world + stop radar publish during pause) so proposals do not become stale while the operator is deciding.

## Changes

- `src/qiki/services/q_sim_service/service.py`
  - Added sim runtime state: running/paused/speed.
  - Implemented `sim.start`, `sim.pause`, `sim.stop`, `sim.reset` in `apply_control_command`.
  - Made `tick()` consult state; during pause/stop it freezes world and stops radar publish.
  - Added `sim_state` into telemetry payload (`TelemetrySnapshotModel` extras).
- `src/qiki/services/q_sim_service/grpc_server.py`
  - Fixed control commands loop to use callback subscription (reliable message handling).
- Tests:
  - `tests/integration/test_sim_pause_effects.py` (integration): pause stops radar frames, start resumes.
  - `src/qiki/services/q_sim_service/tests/test_qsim_service.py` (unit): pause/start/stop/reset toggles state.

## Evidence

Integration test:

`docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'NATS_URL=nats://nats:4222 pytest -q -m integration tests/integration/test_sim_pause_effects.py'`

Output:

```text
.                                                                        [100%]
```

Service logs (selected):

`docker compose -f docker-compose.phase1.yml logs --tail=200 q-sim-service | sed -r 's/\x1b\[[0-9;]*m//g' | rg -n "Applied control command"`

Output:

```text
Applied control command: sim.pause
Applied control command: sim.start
```
