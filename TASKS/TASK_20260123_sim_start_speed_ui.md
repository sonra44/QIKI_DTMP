# TASK: ORION supports simulation.start <speed>

Status: done
Date: 2026-01-23

## Goal

Allow the operator to start simulation with a speed multiplier (e.g. `simulation.start 2`) and make it visible in the ORION header.

## Evidence

Integration (Docker):

```bash
./scripts/run_integration_tests_docker.sh tests/integration/test_sim_start_speed.py
```

Expected output:

```text
.                                                                        [100%]
```

ORION UI (tmux):

- `simulation.start 2` -> header shows `Sim/Сим Running/Работает x2`.

Captured lines (tmux):

```text
command/команда> simulation.start 2
Sim/Сим Running/Работает x2
```
