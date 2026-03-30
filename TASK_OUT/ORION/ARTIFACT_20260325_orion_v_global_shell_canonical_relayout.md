# ARTIFACT: ORION V global shell canonical relayout

Date: 2026-03-25
Status: done

## 1. What existed before the change

Before this pass, the ORION V shell was mounted as a tall always-visible stack:

1. `#orionv-header`
2. `#orionv-actions`
3. `#orionv-bars`
4. `#orionv-overlay`
5. active level widget (`F1/F2/F3/F4/F6/F7`)
6. replay banner
7. help strip
8. command strip

This structure came from the real `compose()` order in `src/qiki/services/operator_console/orion_v/app.py`, not from a design mock.

The result was predictable:

- top chrome consumed too much height;
- alert semantics were truthful but physically too large;
- system summary was useful but lived as a separate heavy global block;
- bottom command/help/status logic was split into multiple zones.

## 2. How the old global shell was structured in actual code

Real shell facts confirmed before editing:

- top zone was assembled in `OrionVApp.compose()`;
- `header.py` rendered a 3-line identity/status block;
- `action_bar.py` rendered global navigation and incident/page controls;
- `status_bars.py` rendered multiple progress-bar rows as always-visible system overview;
- `alerts_overlay.py` rendered expanded multi-line severity-first alert cards with multiple buttons;
- `app.py` also rendered separate `#orionv-help` and `#orionv-command-strip`;
- `F1` and `F2` themselves were not the main shell problem: the shell around them was.

Truth-backed sources already in use before this pass:

- NATS state / event count / current level in header;
- system state from `hardware_view_model` and telemetry;
- objective / incident / QIKI legality driven alerts;
- command/help feedback written through `_set_help_text()`.

## 3. Changed files

Code:

- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/services/operator_console/orion_v/widgets/header.py`
- `src/qiki/services/operator_console/orion_v/widgets/action_bar.py`
- `src/qiki/services/operator_console/orion_v/widgets/status_bars.py`
- `src/qiki/services/operator_console/orion_v/widgets/alerts_overlay.py`

Tests / proof helpers:

- `tests/unit/test_orion_v_header.py`
- `tests/unit/test_orion_v_action_bar.py`
- `tests/unit/test_orion_v_status_bars.py`
- `tests/unit/test_orion_v_cockpit.py`
- `tests/unit/test_orion_v_app_incidents.py`
- `tools/orion_v_top_zone_smoke.py`

## 4. Layout semantics changed

The shell is now physically arranged as:

1. `Mission Control Strip`
2. `Safety & Health Strip`
3. active workspace
4. unified `Action Rail`

Concrete implementation changes:

- `OrionVApp.compose()` now mounts `#orionv-header`, then a single `#orionv-safety-strip`, then the level widgets, then `#orionv-actions` at the bottom.
- Separate always-visible replay/help/command blocks were removed from the outer shell.
- Command input still exists, but now lives inside the bottom rail instead of creating another global strip.

## 5. What moved from global chrome into summary form

Alerts:

- old model: expanded multi-line L0 alert block with per-alert detail and a larger vertical footprint;
- new model: compact alert summary in `alerts_overlay.py`:
  - severity counts `C/W/A`
  - focused alert
  - operator effect
  - short next hint
  - optional focus button for incident-backed alert

Systems:

- old model: multiple progress-bar rows in `status_bars.py`;
- new model: compact subsystem chips:
  - Power
  - Thermal
  - Propulsion
  - Hull
  - Compute
  - QIKI

Each chip now carries only:

- label
- short state
- tiny hint
- severity-colored button variant

## 6. What was unified into the Action Rail

The bottom rail now owns the previously split command/help/status semantics:

- last feedback text from `_set_help_text()`
- command mode state
- operator hint
- screen navigation buttons
- incident/page controls
- inline command shell + open button + input

This closes the command loop in one place instead of spreading it between:

- help strip
- command strip
- navigation strip

## 7. What was intentionally preserved

This pass did not rewrite the content architecture of the main screens:

- `F1` remains cockpit / bridge layer
- `F2` remains systems overview
- `F3` remains deep analysis / incidents
- `F4` remains console
- `F6/F7` remain deeper operational layers

Also intentionally preserved:

- truth-backed alert source logic in `build_level0_alerts()`
- click-to-select incident behavior via overlay focus button
- command mode open/close behavior
- existing `F1` quick-actions

## 8. Proof, tests, lint, compile actually run

### Runtime stack check

Command:

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps
```

Observed:

- `operator-console` healthy
- `qiki-dev` up
- `q-sim-service` healthy
- `q-bios-service` healthy
- NATS healthy

### Ruff

Command:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/services/operator_console/orion_v/app.py \
  src/qiki/services/operator_console/orion_v/widgets/header.py \
  src/qiki/services/operator_console/orion_v/widgets/action_bar.py \
  src/qiki/services/operator_console/orion_v/widgets/status_bars.py \
  src/qiki/services/operator_console/orion_v/widgets/alerts_overlay.py \
  tests/unit/test_orion_v_header.py \
  tests/unit/test_orion_v_action_bar.py \
  tests/unit/test_orion_v_status_bars.py \
  tests/unit/test_orion_v_cockpit.py \
  tests/unit/test_orion_v_app_incidents.py \
  tools/orion_v_top_zone_smoke.py \
  tools/orion_v_command_mode_smoke.py
```

Result:

- `All checks passed!`

### Pytest

Command:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_header.py \
  tests/unit/test_orion_v_action_bar.py \
  tests/unit/test_orion_v_status_bars.py \
  tests/unit/test_orion_v_cockpit.py \
  tests/unit/test_orion_v_app_incidents.py::test_app_mounts_named_top_sections \
  tests/unit/test_orion_v_app_incidents.py::test_command_mode_opens_and_closes_without_persistent_cursor \
  tests/unit/test_orion_v_app_incidents.py::test_overlay_click_selects_incident \
  tests/unit/test_orion_v_app_incidents.py::test_overlay_hides_stale_buttons_after_incident_list_shrinks
```

Result:

- `................................................                         [100%]`

### Compile

Command:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m py_compile \
  src/qiki/services/operator_console/orion_v/app.py \
  src/qiki/services/operator_console/orion_v/widgets/header.py \
  src/qiki/services/operator_console/orion_v/widgets/action_bar.py \
  src/qiki/services/operator_console/orion_v/widgets/status_bars.py \
  src/qiki/services/operator_console/orion_v/widgets/alerts_overlay.py
```

Result:

- success, no compile errors

## 9. Runtime evidence

### `bash scripts/prove_orion_v_top_zone.sh`

Observed:

```text
OK: orion_v_top_zone_smoke
HEADER_TITLE=MISSION CONTROL STRIP
SAFETY_TITLE=SAFETY & HEALTH STRIP
ACTIONS_TITLE=ACTION RAIL
BARS_TITLE=embedded
OVERLAY_TITLE=embedded
COMMAND_STRIP_ID=orionv-command-strip
STATUS_TITLE=Safety & Health: alerts=0 | safe_mode=nominal
```

Interpretation:

- top is no longer a multi-floor stack of independent titled bands;
- alerts and subsystem chips are embedded under one safety strip;
- command semantics are mounted inside the bottom rail.

### `bash scripts/prove_orion_v_f1_body.sh`

Observed:

```text
OK: orion_v_f1_body_smoke
BODY_TITLE=ОБЗОР ПОЛЕТА/FLIGHT OVERVIEW
BODY_SUBTITLE=F1: короткий обзор состояния, затем причина, затем действие
```

Interpretation:

- `F1` body remains intact as the main workspace;
- the shell pass did not collapse cockpit content.

### `bash scripts/prove_orion_v_f1_quick_actions.sh`

Observed:

```text
OK: orion_v_f1_quick_actions_smoke
POWER_BUTTON=Энергия/Power OK -> F2
DOCKING_BUTTON=Стыковка/Docking OK -> F2
COMMS_BUTTON=Связь/Comms WARN -> F2
FINAL_LEVEL=f1
FINAL_SELECTED_MODULE=docking
FINAL_QIKI_STATUS=not_sent
```

Interpretation:

- `F1` quick-actions still route correctly;
- screen architecture and navigation survived the shell relayout.

### `bash scripts/prove_orion_v_command_mode.sh`

Observed:

```text
OK: orion_v_command_mode_smoke
DEFAULT_MODE=no_persistent_input
COMMAND_MODE=open_on_demand
BUTTON_LABEL=Открыть ввод/Open command
```

Interpretation:

- command mode remains on-demand;
- it now lives inside the unified bottom rail instead of its own global strip.

## 10. Honest limitations / unresolved leftovers

1. This pass changes shell semantics and footprint, not the deep text density inside `F1/F2/F3/F4`.
2. `alerts_overlay.py` is now intentionally summary-first; detailed per-alert reading still belongs to deeper layers, not global chrome.
3. The compact chips use current truth-backed summaries from `hardware_view_model`; they do not invent new metrics just to make the strip look fuller.
4. The bottom rail is unified, but it still carries a full button row; if a later pass wants even more workspace height, the next frontier is reducing rail button density, not re-expanding top chrome.

## 11. Architectural verdict

Yes: ORION V is materially closer to the canonical operator shell after this pass.

Acceptance criteria status:

- heavy multi-storey top stack: removed
- compact Mission Control Strip: present
- compact Safety & Health Strip: present
- unified bottom Action Rail: present
- expanded alert block in global chrome: removed
- active workspace height: increased structurally
- `F1/F2/F3/F4/F6/F7` navigation: preserved
- proof paths and checks: executed and recorded

Short architectural conclusion:

- this is no longer a “header + nav + bars + overlay + help + command” shell;
- it is now a canonical operator shell where global chrome is compressed, truth-backed, and subordinate to the active workspace.
