# ARTIFACT: ORION V always-on contract and derived operator state

Date: 2026-03-25
Status: done

## 1. What existed before the change

Before this pass, ORION V already had the new global shell contour from the 2026-03-25 relayout:

1. `Mission Control Strip`
2. `Safety & Health Strip`
3. active workspace
4. `Action Rail`

But the data semantics inside that shell were still split across:

- `app.py` helper methods that manually assembled header values;
- `alerts_overlay.py` summary logic that still lived inside the widget module;
- `status_bars.py` chip logic that read `hardware_model` directly and invented its own chip grammar;
- `action_bar.py` state assembled from separate booleans and strings instead of one operator loop model.

The shell layout had been canonicalized, but the shell state contract had not.

## 2. How the shell received state before the refactor

Confirmed code truth before editing:

- `Mission Control Strip`
  - source: `OrionVApp._refresh_ui()`
  - data came from manual helpers:
    - `_mission_mode_label()`
    - `_control_authority_label()`
    - `_link_anchor_label()`
    - `_telemetry_freshness_seconds()`
    - `_time_anchor_label()`
  - widget API: `OrionVHeader.set_state(...)` with individual presentation args.

- `Safety & Health Strip`
  - `alerts_overlay.py`
    - source mix: `hardware_model`, raw `telemetry`, safe-mode events, active incidents, radar tracks, active objective, QIKI response.
    - summary logic lived in `build_level0_alerts()` inside the widget module.
  - `status_bars.py`
    - source mix: `hardware_model`, safe mode, QIKI legality, pending action title, active alert count.
    - chip grammar lived in `_build_chip_states()` inside the widget module.

- `Action Rail`
  - source: `OrionVApp._refresh_ui()`
  - manual booleans/strings:
    - `current_level`
    - `replay_mode`
    - `has_selected_incident`
    - `incident_controls_visible`
    - `page_controls_visible`
    - `command_mode_open`
    - `status_text`
    - `operator_hint`
    - `selected_incident_id`
    - `selected_subsystem`

## 3. Where raw vs summary were mixed

Main mixed zones found in real code:

- `app.py`
  - manual summary builders for mission/control/link/freshness lived next to runtime event handling.
- `alerts_overlay.py`
  - alert derivation and widget rendering were fused in one module.
- `status_bars.py`
  - chip derivation and widget rendering were fused in one module.
- `action_bar.py`
  - operator loop semantics were flattened into presentation booleans instead of an explicit control-loop object.
- `systems.py`
  - already had useful derived/operator-first card logic, but shell widgets were not consuming a shared normalized shell state.

Truth-backed vs presentation-level aliases before refactor:

- truth-backed
  - `hardware_view_model` subsystem fields and subsystem statuses
  - raw telemetry such as `sim_state`, `comms.latency_ms`, `comms.packet_loss_pct`
  - safe-mode events
  - QIKI legality/pending action
  - active incidents and operator objectives
- presentation-level aliases
  - header mission/control/link strings
  - overlay “focus” summary string
  - chip titles/summaries/severity variants
  - action-rail hotkey hint and command loop text

## 4. Changed files

Code:

- `src/qiki/services/operator_console/orion_v/operator_state.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/services/operator_console/orion_v/widgets/header.py`
- `src/qiki/services/operator_console/orion_v/widgets/alerts_overlay.py`
- `src/qiki/services/operator_console/orion_v/widgets/status_bars.py`
- `src/qiki/services/operator_console/orion_v/widgets/action_bar.py`

Tests:

- `tests/unit/test_orion_v_header.py`
- `tests/unit/test_orion_v_action_bar.py`
- `tests/unit/test_orion_v_status_bars.py`
- `tests/unit/test_orion_v_app_incidents.py`

Artifact:

- `TASK_OUT/ORION/ARTIFACT_20260325_orion_v_always_on_contract_and_derived_state.md`

## 5. Introduced always-on contract

New canonical shell-facing module:

- `src/qiki/services/operator_console/orion_v/operator_state.py`

New shell state path:

`raw telemetry / events / hardware_view_model / qiki / runtime control loop -> build_operator_shell_state(...) -> shell widgets`

Main structures introduced:

- `AlwaysOnOperatorState`
- `DerivedOperatorIndicators`
- `AlertSummary`
- `SubsystemChip`
- `OperatorLoopState`
- `OperatorShellState`
- `OperatorAlert`

The shell now receives one shared contract object:

- `OrionVHeader.set_state(state: OperatorShellState)`
- `OrionVAlertsOverlay.set_state(state: OperatorShellState)`
- `OrionVStatusBars.set_state(state: OperatorShellState)`
- `OrionVActionBar.set_state(state: OperatorShellState)`

Minimum always-on fields now represented explicitly in code:

- Mission / authority
  - `mission_phase`
  - `vehicle_mode`
  - `control_authority`
  - `autopilot_status`
  - `autopilot_mode`
- Freshness / link
  - `link_status`
  - `telemetry_age_ms`
  - `signal_latency_ms`
  - `packet_loss_percent`
  - `last_contact_timestamp`
- Safety
  - `alert_summary`
  - `safe_envelope_state`
  - `emergency_mode`
  - `safe_mode_trigger`
  - `collision_imminent`
- Power
  - `battery_charge_percent`
  - `power_balance_mw`
  - `power_distribution_status`
- Thermal
  - `core_temperature_c`
  - `battery_temp_c`
  - `thermal_load_percent`
- Propulsion / mobility
  - `fuel_remaining_percent`
  - `delta_v_remaining_ms`
  - `engine_status`
  - `propulsion_mode`
- Hull / survivability
  - `hull_integrity_percent`
  - `hull_breach_detected`
- Compute / autonomy
  - `q_core_status`
  - `watchdog_status`
  - `qiki_assist_status`
  - `human_ack_required`
- Operator loop
  - `last_command_status`
  - `operator_action_required`
  - `pending_command_count`

The contract also records:

- `partial_fields`
- `unavailable_fields`

This is how unavailable telemetry is represented honestly instead of being faked.

## 6. Derived indicators implemented for real

Implemented and populated from current code truth:

- Power derived
  - `power_margin_state`
  - `time_to_power_deficit`
  - `time_to_battery_critical`
- Thermal derived
  - `thermal_margin_state`
  - `hotspot_source`
- Navigation / guidance derived
  - `trajectory_deviation`
  - `eta_to_target`
  - `attitude_stability`
- Propulsion derived
  - `maneuver_feasibility`
  - `rcs_authority_available`
- Communications derived
  - `commandability_state`
  - `data_freshness_state`
- Safety derived
  - `intervention_required`
  - `autonomy_confidence`
  - `mission_risk_state`

Real source basis used:

- `hardware_view_model` subsystem fields:
  - power runtime/SOC/draw/available
  - thermal core/warn/trip nodes
  - comms latency/loss
  - docking ETA
  - navigation angular rates
  - propulsion fuel / thrust / active RCS count
  - hull integrity
  - compute load
- raw runtime state:
  - `sim_state`
  - active observation objective `route_role`
- operator loop runtime:
  - pending QIKI requests
  - pending operator confirmation
  - pending control ack
  - running procedure task
- QIKI legality/pending action

## 7. Derived indicators still partial / unresolved

Partial by design because current runtime does not expose enough truth:

- `mission_phase`
  - derived from current `sim_state` runtime label, not from a dedicated mission-phase contract
- `vehicle_mode`
  - currently sourced from available navigation/runtime mode fields when present
- `power_balance_mw`
  - computed from available minus draw when both exist
- `thermal_load_percent`
  - normalized from core temperature vs current thermal threshold
- `engine_status`
  - mapped from propulsion subsystem health, not from a dedicated engine contract
- `qiki_assist_status`
  - mapped from legality/pending action state
- `time_to_battery_critical`
  - estimated from current runtime minutes and SOC
- `trajectory_deviation`
  - derived from objective `route_role`
- `eta_to_target`
  - currently uses available docking ETA surface
- `attitude_stability`
  - derived from current angular-rate fields
- `maneuver_feasibility`
  - derived from propulsion subsystem health + fuel
- `rcs_authority_available`
  - derived from active-count/thrust availability
- `autonomy_confidence`
  - derived from current legality states

Unavailable / unresolved honestly left as gaps:

- `autopilot_status`
- `autopilot_mode`
- `collision_imminent`
- `battery_temp_c`
- `delta_v_remaining_ms`
- `propulsion_mode`
- `hull_breach_detected`
- `q_core_status`
- `watchdog_status`
- `time_to_overheat`
- `fuel_margin_to_plan`
- `collision_risk_score`

These fields now exist in the contract, but remain `None` and are listed in `unavailable_fields` until real runtime truth exists.

## 8. How widgets were moved to the new state contract

### Header

Before:

- widget accepted separate presentation args from `app.py`

After:

- widget reads `OperatorShellState`
- mission/control/link/freshness semantics come from `AlwaysOnOperatorState` and `DerivedOperatorIndicators`

### Alerts overlay

Before:

- widget module both derived alerts and rendered them

After:

- alert derivation moved into `operator_state.py`
- widget is now render-only
- `AlertSummary` is explicit and includes:
  - severity counts
  - `focus_alert`
  - `selected_critical_alert`
  - `action_required`
  - `stale`
  - `unavailable`

### Status bars

Before:

- chip state was assembled inside the widget from raw `hardware_model` + QIKI fragments

After:

- chip derivation moved into `operator_state.py`
- widget now renders explicit `SubsystemChip` objects
- chip model includes:
  - `label`
  - `status`
  - `severity`
  - `short_summary`
  - `hint`
  - `numeric_anchor`
  - `stale`
  - `degraded`
  - action target

Compact chips now explicitly normalize:

- Power
- Thermal
- Propulsion
- Hull
- Compute
- QIKI

### Action Rail

Before:

- widget accepted many booleans and strings from `app.py`

After:

- widget reads explicit `OperatorLoopState`
- action rail now consumes:
  - `last_command_status`
  - `last_command_summary`
  - `pending_command_count`
  - `operator_action_required`
  - `command_mode_state`
  - `hotkey_context`
  - incident/page visibility and selection context

## 9. How `app.py` changed

`app.py` now owns the single shell-state build step:

- `self._operator_shell_state = build_operator_shell_state(...)`

This happens inside `_refresh_ui()` after current truth sources are refreshed.

The app also now tracks explicit operator-loop status:

- `self._last_command_status`
- `self._last_command_summary`
- `self._operator_shell_state`

Those fields are updated when:

- QIKI intent is published
- pending QIKI action is awaiting confirmation
- QIKI action is cancelled
- sim command is sent and awaiting ack
- ack arrives but telemetry effect is still pending
- telemetry confirms command effect
- procedure start is queued
- QIKI response blocks or reopens operator action

## 10. Tests / lint / compile / proof run

### Runtime state check

Command:

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps
curl -s http://127.0.0.1:8222/healthz
```

Observed:

- `operator-console` healthy
- `qiki-dev` up
- `q-sim-service` healthy
- `q-bios-service` healthy
- `nats` healthy
- NATS healthz returned `{"status":"ok"}`

### Ruff

Command:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/services/operator_console/orion_v/operator_state.py \
  src/qiki/services/operator_console/orion_v/app.py \
  src/qiki/services/operator_console/orion_v/widgets/header.py \
  src/qiki/services/operator_console/orion_v/widgets/action_bar.py \
  src/qiki/services/operator_console/orion_v/widgets/status_bars.py \
  src/qiki/services/operator_console/orion_v/widgets/alerts_overlay.py \
  tests/unit/test_orion_v_header.py \
  tests/unit/test_orion_v_action_bar.py \
  tests/unit/test_orion_v_status_bars.py
```

Result:

- `All checks passed!`

### Compile

Command:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m py_compile \
  src/qiki/services/operator_console/orion_v/operator_state.py \
  src/qiki/services/operator_console/orion_v/app.py \
  src/qiki/services/operator_console/orion_v/widgets/header.py \
  src/qiki/services/operator_console/orion_v/widgets/action_bar.py \
  src/qiki/services/operator_console/orion_v/widgets/status_bars.py \
  src/qiki/services/operator_console/orion_v/widgets/alerts_overlay.py
```

Result:

- success, no compile errors

### Unit tests

Commands:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_header.py \
  tests/unit/test_orion_v_action_bar.py \
  tests/unit/test_orion_v_status_bars.py \
  tests/unit/test_orion_v_app_incidents.py

docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_cockpit.py \
  tests/unit/test_orion_v_systems_uses_hardware_model.py
```

Results:

- targeted shell/widget/app pack: green
- cockpit/systems regression pack: `.......................................... [100%]`

### Mandatory proof scripts

Commands:

```bash
bash scripts/prove_orion_v_top_zone.sh
bash scripts/prove_orion_v_f1_body.sh
bash scripts/prove_orion_v_f1_quick_actions.sh
bash scripts/prove_orion_v_command_mode.sh
```

Results:

- all four passed

## 11. Runtime evidence

### `bash scripts/prove_orion_v_top_zone.sh`

Observed:

```text
OK: orion_v_top_zone_smoke
HEADER_TITLE=MISSION CONTROL STRIP
HEADER_SUBTITLE=Identity, active level, authority, link and freshness anchors
SAFETY_TITLE=SAFETY & HEALTH STRIP
ACTIONS_TITLE=ACTION RAIL
BARS_TITLE=embedded
OVERLAY_TITLE=embedded
COMMAND_STRIP_ID=orionv-command-strip
COMMAND_TITLE=ВВОД/INPUT
STATUS_TITLE=Safety & Health: C0/W0/A0 | envelope=nominal | risk=nominal
QIKI_CONFIRM=QIKI: нет действия/No action
```

Interpretation:

- shell contour remained intact
- safety strip now renders explicit normalized summary semantics
- command strip remains embedded inside action rail

### `bash scripts/prove_orion_v_f1_body.sh`

Observed:

```text
OK: orion_v_f1_body_smoke
BODY_TITLE=ОБЗОР ПОЛЕТА/FLIGHT OVERVIEW
BODY_SUBTITLE=F1: короткий обзор состояния, затем причина, затем действие
```

Interpretation:

- F1 body contract remained stable
- shell refactor did not collapse cockpit content

### `bash scripts/prove_orion_v_f1_quick_actions.sh`

Observed:

```text
OK: orion_v_f1_quick_actions_smoke
POWER_BUTTON=Энергия/Power OK -> F2
DOCKING_BUTTON=Стыковка/Docking OK -> F2
COMMS_BUTTON=Связь/Comms CRIT -> F2
FINAL_LEVEL=f1
FINAL_SELECTED_MODULE=docking
```

Interpretation:

- F1 quick actions still route into the expected subsystem/detail path
- state refactor did not break quick-action semantics

### `bash scripts/prove_orion_v_command_mode.sh`

Observed:

```text
OK: orion_v_command_mode_smoke
DEFAULT_MODE=no_persistent_input
COMMAND_MODE=open_on_demand
BUTTON_LABEL=Открыть ввод/Open command
```

Interpretation:

- command-mode behavior stayed compatible with the post-relayout shell
- action rail still owns the command loop

## 12. Honest limitations / remaining gaps

- The shell contract is now explicit, but not every requested field has runtime truth yet.
- Some always-on fields still come from derived aliases over current runtime state, not from dedicated upstream DTOs.
- `q_core_status` and `watchdog_status` remain unresolved because the current ORION V path does not expose a stable shell-facing truth field for them.
- `collision_risk_score`, `time_to_overheat`, and `fuel_margin_to_plan` are intentionally left unresolved rather than guessed.
- `eta_to_target` is currently the available docking ETA surface, not a general mission ETA contract.
- `vehicle_mode` and `mission_phase` are still sourced from current runtime/nav surfaces, not from a dedicated canonical mission DTO.

## 13. Architectural verdict

Yes, ORION V is materially closer to an operator-grade state model after this pass.

Why:

- shell widgets no longer assemble their own scattered truth fragments;
- `app.py` now builds one explicit shell-facing operator state bundle;
- alert summary is a real model, not an ad hoc string;
- subsystem chips are a real normalized model, not widget-local composition;
- action rail now reads an explicit operator control-loop state;
- derived indicators now exist as a named layer between raw/runtime truth and shell summaries;
- unavailable fields are carried honestly as gaps, not faked telemetry.

Resulting architecture:

`raw telemetry + events + hardware_view_model + qiki + operator loop runtime -> operator_state.py -> shell widgets + summary surfaces`
