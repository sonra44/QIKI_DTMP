# Telemetry G1 Implementation Lock (Canon)

Status: active
Date: 2026-03-01
Scope: ORION V + qiki.telemetry runtime contract alignment

## Purpose

This document locks the mandatory G1 telemetry scope and records current implementation coverage.
It exists to prevent context drift and repeated "planned but not wired" loops.

Important:
- `docs/design/operator_console/TELEMETRY_DICTIONARY.yaml` remains no-placeholders (only real runtime fields).
- This lock defines required backlog until fields are present in runtime/schema.

## Locked G1 mandatory additions

1. Velocity model:
- `velocity_xyz_m_s` + `speed_m_s` (vector + scalar consistency).
- `velocity` сохраняется как legacy scalar alias для обратной совместимости.

2. Orbit derived metrics (+ confidence):
- `orbit.apoapsis_km`
- `orbit.periapsis_km`
- `orbit.inclination_deg`
- `orbit.eccentricity`
- `orbit.period_min`

3. Split battery channels:
- `power.battery_1_voltage_v`
- `power.battery_2_voltage_v`

4. Comms link metrics:
- `comms.rssi_dbm`
- `comms.snr_db`
- `comms.tx_power_w`
- `comms.data_rate_kbps`
- `comms.antenna_status`

5. Propulsion constraints:
- `propulsion.propellant_tank_pressure_pa`
- `propulsion.oxidizer_mass_kg`

6. Safety authority:
- `safe_mode` authoritative source = Q-Core Agent.

7. Truth semantics:
- Runtime/game states: `healthy|degraded|failed|off` + reason.
- `N/A` only for dev/contract error.

## Coverage snapshot (2026-03-01)

Already present in runtime payload / models:
- `position.{x,y,z}` (telemetry model)
- scalar `velocity` + `speed_m_s` + `velocity_xyz_m_s.{x,y,z}` + `heading`
- `attitude.{roll,pitch,yaw}_rad`
- `power.*` core SoC/bus/in-out/faults/shed/supercap/dock/NBL + split battery voltage channels
- `thermal.nodes[*]`
- `propulsion.{propellant_tank_pressure_pa,oxidizer_mass_kg,rcs.*}`
- `comms.{link,latency_ms,packet_loss_pct,rssi_dbm,snr_db,tx_power_w,data_rate_kbps,antenna_status,xpdr.*}`
- `orbit.{state,reason,confidence,apoapsis_km,periapsis_km,inclination_deg,eccentricity,period_min}`
- `sensor_plane.*` baseline (imu/radiation/proximity/solar/star_tracker/magnetometer)
- `cpu_usage`, `memory_usage`, `radiation_usvh`

Missing or partial vs locked G1:
- Orbit quality remains `degraded`/`off` in non-orbital dynamics and is intentionally flagged by `orbit.state/reason/confidence`.
- Safe-mode authority now surfaced in ORION V via `qiki.events.v1.*` (SAFE_MODE/FSM transition signals from Q-Core) across F1/F2/F3 views.
- Safe-mode integration into `qiki.telemetry` payload itself remains downstream (no dual-source in q-sim).

## Implementation sequence (strict)

1) Runtime source first:
- add fields to q_sim_service and/or q_core source of truth.

2) Contract second:
- update telemetry schema/model and compatibility handling.

3) Dictionary third:
- add only fields that truly exist in payloads to TELEMETRY_DICTIONARY.

4) UI fourth:
- wire ORION V screens and explain/gating logic.

5) Evidence:
- unit + integration + runtime smoke with payload proof.

No step skipping is allowed.

## Acceptance gates

A change is not "done" unless all pass:
1. Runtime emits field in real payload.
2. Contract/model validates it.
3. Dictionary includes it.
4. ORION V displays it with correct units/state semantics.
5. Evidence is recorded in TASKS dossier and memory recall-proof IDs.
