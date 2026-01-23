# TASK: Validate simulation.reset semantics

Status: done
Date: 2026-01-23

## Goal

Make `simulation.reset/симуляция.сброс` deterministic and evidenced:

- Reset does not auto-start the sim.
- Reset while STOPPED clears world state (attitude to 0, position to 0).

## Evidence

Integration test (Docker):

```bash
./scripts/run_integration_tests_docker.sh tests/integration/test_sim_reset_effects.py
```

Expected output:

```text
.                                                                        [100%]
```

ORION UI (tmux) evidence:

- `simulation.stop` -> `Sim/Сим Stopped/Остановлено` and Roll/Pitch are non-zero.
- `simulation.reset` -> `Sim/Сим` stays `Stopped/Остановлено` and Roll/Pitch become `0.0°`.

Captured lines (tmux):

```text
Sim/Сим Stopped/Остановлено
Roll/Крен               1.6°
Pitch/Тангаж            1.2°
command/команда> simulation.stop

Sim/Сим Stopped/Остановлено
Roll/Крен               0.0°
Pitch/Тангаж            0.0°
command/команда> simulation.reset
```
