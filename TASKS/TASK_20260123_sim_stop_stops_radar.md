# TASK: sim.stop stops radar frames

Status: done
Date: 2026-01-23

## Goal

Prove deterministically that `sim.stop` (via `simulation.stop`) stops radar publishing (no `qiki.radar.v1.frames`) and that `sim.start` resumes it.

## Evidence

Integration (Docker):

```bash
./scripts/run_integration_tests_docker.sh tests/integration/test_sim_stop_effects.py
```

Expected output:

```text
.                                                                        [100%]
```
