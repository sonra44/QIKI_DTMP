# QIKI_DTMP — Design Canon Index (Active Entry Point)

This file exists as a stable **design canon entrypoint** referenced by session bootstrap docs (`~/MEMORI/ПРОЧТИ_ЭТО_QIKI_DTMP.md`).

## Single entrypoint (recommended)

- Canonical documentation reading order: `docs/INDEX.md`

## Active design areas (design canon)

- ORION Operator Console: `docs/design/operator_console/`
- Bot “hardware / physics” (Digital Twin contract): `docs/design/hardware_and_physics/`
- Q-Core Agent: `docs/design/q-core-agent/`
- Game layer (lore/intent): `docs/design/game/`

## Hardware / Physics canon

QIKI Body v0.2.2 defines the current target documentation canon for QIKI body hardware / physics / machine-body constraints.

See:

`../hardware_and_physics/qiki_body_v0_2_2/00_INDEX.md`

Scope:

body geometry, mass, CoM, inertia, power, thermal, RCS, bayonet, NBL, protection, modularity, command gating, ORION Evidence, audit and blackbox.

Runtime conformance is not claimed by this documentation package.

## Canon decisions (ADR)

- ADR directory: `docs/design/canon/ADR/`
- Execution-critical (2026-07-10, «бумажный» срез):
  - `ADR/ADR_2026-07-10_brake_override_emergency_command_path.md` — аварийный короткий путь одобрения (гейт этапа 9)
  - `ADR/ADR_2026-07-10_target_identity_layer07_ownership.md` — владелец Layer-07 fusion = мозг; S1-мини = гейт этапа 9b
  - `ADR/ADR_2026-07-10_tick_owner_single_brain.md` — владелец тика = qiki-dev; intents = проекция
- Context lock (cross-session anti-drift): `docs/design/canon/CONTEXT_LOCK_QIKI_DTMP.md`
- Telemetry G1 implementation lock: `docs/design/canon/TELEMETRY_G1_IMPLEMENTATION_LOCK.md`
- Current product-critical execution canons:
  - `docs/design/canon/G1_QIKI_OPERATOR_LOOP_CANON.md`
  - `docs/design/canon/G1_QIKI_PROCEDURAL_EXECUTION_CANON.md`
  - `docs/design/canon/G2_QIKI_PROTOCOL_ARBITRATION_CANON.md`
  - `docs/design/canon/G2_QIKI_HOSTILE_CONTEXT_OPEN_CANON.md`
  - `docs/design/canon/G2_QIKI_COMBAT_ENTRY_PREP_CANON.md`
  - `docs/design/canon/G2_QIKI_COMBAT_RESOURCE_GATE_CANON.md`
  - `docs/design/canon/G2_QIKI_TACTICAL_STATE_SHIFT_CANON.md`
  - `docs/design/canon/G2_QIKI_COMBAT_EVENT_CONSEQUENCE_CANON.md`
  - `docs/design/canon/G2_QIKI_COMBAT_SYSTEM_CONSEQUENCE_CANON.md`
  - `docs/design/canon/G2_QIKI_THERMAL_OR_POWER_CONSTRAINT_CANON.md`
  - `docs/design/canon/G2_QIKI_THERMAL_CONSTRAINT_FOLLOWUP_CANON.md`
  - `docs/design/canon/G2_QIKI_COMMS_COMBAT_CONSTRAINT_CANON.md`

## Canon spotlights (selected)

- Radar visualization strategy/spec: `docs/design/operator_console/RADAR_VISUALIZATION_RFC.md`
- QIKI Body v0.2.2 (machine body — hardware/physics): **target canon, documentation-only, runtime conformance NOT claimed** — `docs/design/hardware_and_physics/qiki_body_v0_2_2/00_INDEX.md`
- ORION V clickable UX acceptance: `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_CHECKLIST.md`
- Terminal game narrative canon: `docs/design/game/SECTOR_TERTA_CANON.md`

## Non-canon / reference

- Any historical/archive docs (including `docs/Архив/**` when present) are **REFERENCE ONLY (NOT CANON)**.
- Active canon is defined only by this index and linked canon entrypoints.
