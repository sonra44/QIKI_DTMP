# ARTIFACT: ORION V F1 mission cockpit refactor

Date: 2026-03-25
Status: done

## 1. What F1 was before the change

Before this pass, `F1` in `src/qiki/services/operator_console/orion_v/screens/cockpit.py` was still a mixed screen even after the shell relayout and the new always-on operator state contract.

Real structure before editing:

- a full-width `#orionv-cockpit-actions` block on top;
- one large text body `#orionv-cockpit-body`;
- the body started with six scene-oriented zones:
  - `Mode / Context`
  - `Available Actions`
  - `Current Process`
  - `Spatial Telemetry`
  - `Route / Intent`
  - `QIKI Interpretation`
- then `F1` kept expanding into another long diagnostics tail:
  - observation objective
  - linked facts
  - QIKI command loop
  - procedure
  - safety
  - incidents
  - power
  - motion/navigation
  - comms
  - thermal

That meant the top of `F1` tried to be mission-facing, but the same screen still kept dashboard residue and subsystem-heavy detail that properly belongs in `F2/F3`.

## 2. Actual structure of the old cockpit screen

Facts from the old code path:

- `OrionVCockpitScreen.compose()` mounted a full-width quick-actions panel above the body.
- `OrionVCockpitScreen.set_state()` consumed raw telemetry, incidents, safe-mode payload, observation objective, QIKI response, procedure status, and timeline lines directly.
- `OrionVCockpitScreen._refresh_text()` assembled one long plain-text screen by concatenating many helper blocks.
- `app.py` already built `OperatorShellState`, but `F1` was not using that normalized shell state as its main semantic base.

## 3. What in old F1 was mission-facing vs dashboard residue

Mission-facing and genuinely useful:

- observation objective lifecycle and follow-up/result semantics;
- route/target meaning from the active observation objective;
- QIKI legality / trust / consequence loop;
- procedure execution status;
- selected/critical incident presence.

Dashboard residue / systems leakage:

- full-width quick-actions strip dominating the top of the screen;
- large power/comms/thermal/safety blocks repeated after shell strips already exposed compact always-on state;
- system detail that duplicated `F2` instead of staying mission-primary;
- mixed composition where operator intervention, mission narrative, and subsystem truth anchors were not clearly separated.

## 4. Files changed

Code:

- `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
- `src/qiki/services/operator_console/orion_v/app.py`

Proof helpers:

- `tools/orion_v_f1_body_smoke.py`
- `tools/orion_v_f1_quick_actions_smoke.py`

Artifact:

- `TASK_OUT/ORION/ARTIFACT_20260325_orion_v_f1_mission_cockpit_refactor.md`

## 5. How the new F1 layout works

`F1` is now physically split into two columns inside `#orionv-cockpit-layout`:

### Left column: `MISSION / COCKPIT`

This is the main mission narrative lane. It now leads with:

- `Mission Context`
- `Guidance / Movement`
- `Mission Incident Focus`

Only after that does it keep supporting truth anchors:

- `Mode / Context`
- `Route / Intent`
- `Spatial Telemetry`
- `Mission Support Truth`
- `Observation Objective`

The important change is not “remove all details”, but “make mission interpretation primary and diagnostics secondary”.

### Right column: `OPERATOR / INTERVENTION LANE`

This is the operator action lane. It now carries:

- compact immediate action buttons;
- `Autonomy / QIKI Recommendation`;
- `Operator Intervention`;
- `Available Actions`;
- `Current Process`;
- `QIKI Interpretation`;
- `Procedure`.

Quick actions are no longer a full-width top band that breaks the composition of the mission screen.

## 6. What F1 now takes from operator state / derived indicators

`app.py` now passes the already-built `OperatorShellState` into `OrionVCockpitScreen.set_state(...)`.

`F1` now uses the normalized shell contract as the primary semantic source for:

- `mission_phase`
- `control_authority`
- `mission_risk_state`
- `autopilot_status` / `autopilot_mode` when present
- `vehicle_mode`
- `eta_to_target`
- `trajectory_deviation`
- `attitude_stability`
- `maneuver_feasibility`
- `commandability_state`
- `autonomy_confidence`
- `qiki_assist_status`
- `human_ack_required`
- `intervention_required`
- `OperatorLoopState` values:
  - `last_command_status`
  - `last_command_summary`
  - `pending_command_count`
  - `command_mode_state`
  - selected incident / subsystem context
- focused shell alert via `alert_summary.focus_alert` / `selected_critical_alert`

`F1` still uses direct truth-backed local inputs where the shell contract does not yet project a dedicated field:

- observation objective payload
- objective timeline lines
- QIKI response payload
- telemetry docking distance / closing rate fallback

## 7. What was deliberately removed or weakened

Intentional reductions:

- removed the full-width quick-actions block as the main top composition element;
- reduced systems-heavy material to a lower `Mission Support Truth` appendix instead of letting it define the screen;
- stopped treating `F1` as a place for large parallel system summaries when the shell and `F2` already cover that territory;
- kept the operator mission question at the top instead of leading with generic action cards.

## 8. What moved into the right intervention lane

The right lane now owns the operator-response semantics:

- mission-relevant jump buttons;
- QIKI confirm / cancel;
- autonomy confidence and ack requirement;
- next command relevance;
- operator loop state;
- procedure state and command-loop readiness.

This directly answers:

- what can I do right now,
- what does QIKI recommend,
- where does the human need to confirm or take over.

## 9. Checks, lint, compile, tests, proof actually run

### Stack state

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps
```

Observed during the pass:

- `qiki-operator-console` healthy
- `qiki-dev-phase1` up
- `qiki-sim-phase1` healthy
- `qiki-bios-phase1` healthy
- supporting phase1 stack alive

### Ruff

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/services/operator_console/orion_v/screens/cockpit.py \
  src/qiki/services/operator_console/orion_v/app.py \
  tests/unit/test_orion_v_cockpit.py \
  tests/unit/test_orion_v_app_incidents.py \
  tools/orion_v_f1_body_smoke.py \
  tools/orion_v_f1_quick_actions_smoke.py
```

Result:

- `All checks passed!`

### Compile

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m py_compile \
  src/qiki/services/operator_console/orion_v/screens/cockpit.py \
  src/qiki/services/operator_console/orion_v/app.py \
  tools/orion_v_f1_body_smoke.py \
  tools/orion_v_f1_quick_actions_smoke.py
```

Result:

- success, no compile errors

### Targeted pytest

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_cockpit.py \
  tests/unit/test_orion_v_app_incidents.py \
  tests/unit/test_orion_v_action_bar.py \
  tests/unit/test_orion_v_header.py \
  tests/unit/test_orion_v_status_bars.py
```

Result:

- green full run for the F1/shell-related unit and integration pack

### Required proof scripts

```bash
bash scripts/prove_orion_v_f1_body.sh
bash scripts/prove_orion_v_f1_quick_actions.sh
bash scripts/prove_orion_v_top_zone.sh
bash scripts/prove_orion_v_command_mode.sh
```

Result:

- all four scripts passed after adapting the two F1 smoke helpers to the new mission/intervention layout

## 10. Runtime evidence

### `bash scripts/prove_orion_v_f1_body.sh`

Observed:

```text
OK: orion_v_f1_body_smoke
BODY_TITLE=MISSION / COCKPIT
BODY_SUBTITLE=Что аппарат делает сейчас, куда идёт и срывается ли mission flow.
INTERVENTION_TITLE=OPERATOR / INTERVENTION LANE
INTERVENTION_SUBTITLE=Что рекомендует автоматика, что можно сделать сейчас и где нужен человек.
LINE_1= Mission / Cockpit
LINE_2=СИСТЕМА: КРИТИЧНО | System: Есть критические инциденты, требуется немедленное подтверждение.
RIGHT_LINE_1= Operator / Intervention Lane
RIGHT_LINE_2=Immediate actions live on the right rail: click mission-relevant jump buttons, then confirm/cancel QIKI only when the state is truth-backed.
```

Meaning:

- `F1` is no longer titled as a generic overview;
- it now exposes an explicit mission body plus a separate intervention lane.

### `bash scripts/prove_orion_v_f1_quick_actions.sh`

Observed:

```text
OK: orion_v_f1_quick_actions_smoke
POWER_BUTTON=Power Margin OK -> F2
DOCKING_BUTTON=Target/Docking OK -> F2
COMMS_BUTTON=Comms Link WARN -> F2
QIKI_CONFIRM_READY=QIKI: нет действия/No action
INTERVENTION_HAS_PREPARED=1
FINAL_LEVEL=f1
FINAL_SELECTED_MODULE=docking
FINAL_QIKI_STATUS=not_sent
```

Meaning:

- quick actions now read as operator/missions aids rather than decorative cockpit chrome;
- confirm/cancel semantics still work;
- F1 navigation to `F2` remains intact.

### `bash scripts/prove_orion_v_top_zone.sh`

Observed:

```text
OK: orion_v_top_zone_smoke
HEADER_TITLE=MISSION CONTROL STRIP
SAFETY_TITLE=SAFETY & HEALTH STRIP
ACTIONS_TITLE=ACTION RAIL
COCKPIT_ACTIONS_TITLE=IMMEDIATE ACTIONS / INTERVENTION
QIKI_CONFIRM=QIKI: нет действия/No action
```

Meaning:

- the canonical shell contour stayed intact;
- the cockpit refactor did not regress the global shell layout.

### `bash scripts/prove_orion_v_command_mode.sh`

Observed:

```text
OK: orion_v_command_mode_smoke
DEFAULT_MODE=no_persistent_input
COMMAND_MODE=open_on_demand
BUTTON_LABEL=Открыть ввод/Open command
```

Meaning:

- the bottom command loop still behaves as before;
- the F1 refactor did not break command-mode navigation.

## 11. Honest limitations / missing mission data

This pass did not invent missing mission truth.

Still partial or absent:

- no dedicated mission-phase runtime contract; `mission_phase` is still derived from current runtime/sim context;
- no dedicated guidance-state contract; `F1` falls back through autopilot fields, guidance telemetry, docking state, then vehicle mode;
- no guaranteed mission-wide target distance; `F1` uses observation `track_range_m` first, then docking distance fallback;
- no guaranteed mission-wide closing rate; `F1` uses docking approach / relative speed fallback only when that contour exists;
- `autopilot_status`, `autopilot_mode`, `collision_imminent`, `fuel_margin_to_plan` remain honest gaps in the current shell state for many runtime contours;
- collision-risk semantics are still not truth-backed enough for a stronger mission hazard line in `F1`.

Those limitations are surfaced as partial/gap text instead of being faked.

## 12. Architectural verdict

Yes: `F1` is now materially closer to a real mission cockpit.

Why:

- the screen now answers the mission-first operator question at the top;
- mission narrative and operator intervention are separated into left/right lanes;
- shell-derived state is now a real semantic input to `F1`, not just to always-on widgets;
- full-width dashboard-like quick actions were removed from the top composition;
- heavy subsystem detail was weakened into lower truth anchors instead of dominating the cockpit;
- navigation and canonical shell layout remained intact.

What is still logically next:

- add a dedicated mission/guidance projection into the operator-state contract when the runtime exposes stronger truth for distance / closing / maneuver / mission-phase fields;
- then narrow the remaining support appendix further so `F1` can become even more mission-dense without losing honest traceability.
