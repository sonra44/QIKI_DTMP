# ORION Simulation Control Contract (Phase 1)

This document is the single source of truth for how ORION controls the simulation and how the simulation state is surfaced back to the operator.

Scope:

- Operator Console (ORION) command dock + header.
- Simulation service (`q_sim_service`) runtime state machine.
- NATS control bus + telemetry.

Non-goals:

- No auto-actions.
- No execution beyond simulation runtime control.

## Source of truth

- The simulation single source of truth is `q_sim_service`.
- ORION is UI-only: it only publishes control commands and renders state from telemetry.

## Operator commands (ORION)

All commands are entered in ORION input (`command/команда>`). Use `Ctrl+E` to focus the input.

### `simulation.start [speed]` (aka `sim.start` / `симуляция.старт`)

Starts RUNNING mode.

- Without an argument, defaults to speed `1.0`.
- With an argument, sets a speed multiplier.

Accepted speed forms:

- `simulation.start 2`
- `simulation.start x2`
- `simulation.start 2x`
- `simulation.start speed=2`

Rules:

- speed must be a positive float; invalid values are rejected in ORION.

### `simulation.pause` (aka `sim.pause` / `симуляция.пауза`)

Sets PAUSED mode.

Semantics:

- World does not advance.
- Radar frames are not published.
- Telemetry keeps flowing (with `sim_state` showing PAUSED).

### `simulation.stop` (aka `sim.stop` / `симуляция.стоп`)

Sets STOPPED mode.

Semantics:

- World does not advance.
- Radar frames are not published.
- Telemetry keeps flowing (with `sim_state` showing STOPPED).

### `simulation.reset` (aka `sim.reset` / `симуляция.сброс`)

Destructive command: resets the world state.

Safety:

- ORION always shows a ConfirmDialog (Y/N). Only `y` publishes `sim.reset`.

Semantics (canonical decision):

- Reset implies STOPPED (reset = stop + clear world).
- World state returns to initial values (position 0,0,0; attitude 0; internal queues cleared).

## NATS control bus

ORION publishes a `CommandMessage` JSON to:

- subject: `qiki.commands.control`

Destination routing:

- `sim.*` and `power.*` commands target `q_sim_service`.

### Control ACK envelope (P0, backward-compatible)

`q_sim_service` publishes a control ACK JSON to:

- subject: `qiki.responses.control`

Contract goals:
- Keep **both** legacy and new aliases in the same message (no `v2`, no new subjects).
- Make UI parsing deterministic and replay-friendly.

Required top-level fields:
- `version`: `1`
- `kind`: `"<command_name>"`
- `timestamp`: RFC3339/ISO string (UTC)
- `requestId` and `request_id`: same UUID (aliases)
- `success` and `ok`: same bool (aliases)
- `payload`: dict with at least:
  - `command_name`
  - `status` (e.g. `applied`, `rejected`, `exception: ...`)

Error fields (only when `ok=false`):
- `error`: legacy string code (fallback)
- `error_detail`: structured dict:
  - `code`
  - `message`
  - `details` (dict)

Deterministic evidence:
- Unit: `src/qiki/services/q_sim_service/tests/test_control_responses.py`
- Integration (NATS): `tests/integration/test_control_ack_envelope.py`

## Telemetry and UI rendering

`q_sim_service` publishes telemetry snapshots to:

- subject: `qiki.telemetry`

Telemetry payload is validated by `TelemetrySnapshotModel` and allows extra top-level keys. The simulation runtime state is carried as an extra key:

- `sim_state`:
  - `fsm_state`: `RUNNING|PAUSED|STOPPED`
  - `running`: bool
  - `paused`: bool
  - `speed`: float

ORION header rendering (`Sim/Сим`):

- `RUNNING` -> `Running/Работает` (+ `xN` when speed != 1.0)
- `PAUSED` -> `Paused/Пауза` (+ `xN` when speed != 1.0)
- `STOPPED` -> `Stopped/Остановлено`

## Radar publishing rules

Radar frames (`qiki.radar.v1.frames` and LR/SR split subjects) are published only when:

- sim state is RUNNING, and
- radar is enabled (`RADAR_ENABLED=1` and `RADAR_NATS_ENABLED=1`).

During PAUSED/STOPPED there must be no new `qiki.radar.v1.frames`.

## Deterministic evidence (tests)

Integration tests are deselected by default via `pytest.ini`. Use the wrapper:

```bash
./scripts/run_integration_tests_docker.sh tests/integration/test_sim_pause_effects.py
./scripts/run_integration_tests_docker.sh tests/integration/test_sim_stop_effects.py
./scripts/run_integration_tests_docker.sh tests/integration/test_sim_reset_effects.py
./scripts/run_integration_tests_docker.sh tests/integration/test_sim_start_speed.py
```

Quality gate (includes integration):

```bash
QUALITY_GATE_RUN_INTEGRATION=1 bash scripts/quality_gate_docker.sh
```
