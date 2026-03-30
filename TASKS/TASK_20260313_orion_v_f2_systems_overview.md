# TASK: ORION V F2 Systems Overview

Status: done
Date: 2026-03-13
Owner: Codex

## Goal

Turn existing `F2` in ORION V from a hardware field dump into an operator-first systems overview layer built only on current truth-backed sources.

## Scope Lock

- No `orion_v2`
- No new truth source
- No deep subsystem rewrite
- No raw debug dump as the main F2 surface
- Minimal live F2 only: overview cards, summary builders, existing telemetry/objective/safe-mode/radar context

## Canonical F2 Cards

1. `Docking / Dock Interface`
2. `Power / Charge`
3. `Propulsion / Motion`
4. `Navigation / Route`
5. `Sensors / Radar / Observation`
6. `Comms / Link / Protocol`
7. `Safety / Integrity / Hazard`

## Card Grammar

Each card must show:

- subsystem name
- current status
- severity
- short summary
- operational effect
- next attention
- optional quick hint

## Source Map

- `Docking / Dock Interface`
  - raw: `hardware_view_model.docking`, `qiki.telemetry.docking.*`, `power.dock_bridge_state`
  - derived: dock summary + scene profile + dock bridge context
- `Power / Charge`
  - raw: `hardware_view_model.power`, `qiki.telemetry.power.*`, dock state
  - derived: runtime/load-shed interpretation + charging context
- `Propulsion / Motion`
  - raw: `hardware_view_model.propulsion`, selected motion fields already aggregated there
  - derived: burn margin + maneuver authority meaning
- `Navigation / Route`
  - raw: `hardware_view_model.navigation`, active observation objective, follow-up/result fields, `qiki.telemetry.docking/orbit.*`
  - derived: scene profile + route contour + action gate meaning
- `Sensors / Radar / Observation`
  - raw: `hardware_view_model.sensors`, live radar tracks, active observation objective
  - derived: observation target/live picture context
- `Comms / Link / Protocol`
  - raw: `hardware_view_model.comms`, `qiki.telemetry.comms.*`
  - derived: freshness/loss/latency quality meaning
- `Safety / Integrity / Hazard`
  - raw: `hardware_view_model.hull`, safe-mode event state, active incidents
  - derived: safety authority + hazard aggregation

## Implementation Notes

- `src/qiki/services/operator_console/orion_v/screens/systems.py`
  - replaced old top-fields dump with 7 operator-first system cards
  - cards now sort by severity first, then canonical order
  - added route/objective/radar/safe-mode/incidents aware summaries
- `src/qiki/services/operator_console/orion_v/app.py`
  - `F2` now receives telemetry, active objective, incidents, and live radar tracks in addition to `hardware_model`
- `tests/unit/test_orion_v_systems_uses_hardware_model.py`
  - rewritten around the new card grammar and docked/route-sensitive behavior

## Honest Limitations

- No unified route ETA truth exists yet
- `rlsm` is still not a live subsystem in current collector truth
- `orbital_hold` remains an upstream runtime gap and is not treated as a blocker for F2

## Evidence

- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_systems_uses_hardware_model.py tests/unit/test_orion_v_cockpit.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/operator_console/orion_v/screens/systems.py tests/unit/test_orion_v_systems_uses_hardware_model.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m py_compile src/qiki/services/operator_console/orion_v/screens/systems.py src/qiki/services/operator_console/orion_v/app.py`
- Live tmux proof:
  - `orionv_f2_0313:0.0` pane `%77` -> baseline `docked` F2 (`Docking / Dock Interface` shows `station interface engaged`)
  - `orionv_f2_route_gate_0313:0.0` pane `%79` -> route-sensitive F2 with hydrated `qiki.events.v1.operator.objectives` (`Navigation / Route` rises to the top with `review gate active`)

## Architectural Verdict

- `F2` is now a real systems overview layer, not a raw hardware dump.
- The layer is fundamental enough to sit after scene-based `F1`: it explains subsystem state in terms of operator impact and next attention.
- What is still missing before deeper circles:
  - unified route ETA truth
  - live `rlsm` subsystem truth
  - richer route-sensitive cards for more than one objective contour
- Logical next steps after this slice:
  - alerts overlay refinement
  - object/target panel
  - action/consequence refinement
  - only then deeper subsystem metrics where truth is already stable
