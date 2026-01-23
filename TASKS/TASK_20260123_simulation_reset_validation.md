# TASK: Validate simulation.reset semantics

Status: done
Date: 2026-01-23

## Goal

Make `simulation.reset/симуляция.сброс` deterministic and evidenced:

- Reset implies STOPPED (no auto-running after reset).
- Reset clears world state (attitude to 0, position to 0).

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

- While running: Roll/Pitch become non-zero.
- `simulation.reset` -> ConfirmDialog (`y`) -> `Sim/Сим` becomes `Stopped/Остановлено` and Roll/Pitch become `0.0°`.

Captured lines (tmux):

```text
Sim/Сим Running/Работает
Roll/Крен               1.9°
Pitch/Тангаж            1.0°

Sim/Сим Stopped/Остановлено
Roll/Крен               0.0°
Pitch/Тангаж            0.0°
command/команда> simulation.reset
```
