# TASK: ORION header shows sim state

Status: done
Date: 2026-01-23

## Goal

Show simulation runtime state (RUNNING/PAUSED/STOPPED) in ORION header so the operator can see active pause at a glance.

## Change

- `src/qiki/services/operator_console/main_orion.py`
  - Added header cell `hdr-sim` showing `Sim/Сим` with bilingual state.
  - State is derived from telemetry extra `sim_state` (published by `q_sim_service`).

## Evidence

In ORION (attached via `docker attach qiki-operator-console`):

1) Send `simulation.pause` -> header shows `Sim/Сим Paused/Пауза`.
2) Send `simulation.start` -> header shows `Sim/Сим Running/Работает`.
