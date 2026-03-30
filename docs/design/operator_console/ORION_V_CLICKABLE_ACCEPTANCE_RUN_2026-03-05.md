# ORION V Clickable Acceptance Run — 2026-03-05

Status: pass
Date: 2026-03-05
Scope: `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_CHECKLIST.md`

## Environment

- terminal: Docker/headless test runner + tmux runtime pane capture
- transport: local Docker network
- tmux profile: historical runtime capture from session `0`, pane `%7`, size `311x90`
- stack: `docker-compose.phase1.yml` + `docker-compose.operator.yml`
- small geometry proof: Textual `run_test` at `140x44`

## Commands

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console

docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps operator-console qiki-dev q-sim-service q-bios-service

docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_status_bars.py \
  tests/unit/test_orion_v_app_incidents.py \
  tests/unit/test_orion_v_cockpit.py \
  tests/unit/test_orion_v_deep_dive.py \
  tests/unit/test_orion_v_raw.py \
  tests/unit/test_orion_v_systems_uses_hardware_model.py

docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/services/operator_console/orion_v/widgets/status_bars.py \
  tests/unit/test_orion_v_status_bars.py \
  tests/unit/test_orion_v_app_incidents.py \
  docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_CHECKLIST.md

PANE_ID="$(tmux list-panes -a -F '#{pane_id} #{pane_current_path} #{pane_current_command}' | rg '/home/sonra44/QIKI_DTMP .*python|/home/sonra44/QIKI_DTMP .*bash' | head -n1 | cut -d' ' -f1)"
tmux capture-pane -p -t "$PANE_ID" -S -240 | rg -n "SKELETON/СКЕЛЕТ|Power/EPS|Thermal|Comms|Hull|Incidents/Инциденты" -A6 -B2

bash scripts/prove_orion_v_f1_quick_actions.sh
```

## Runtime Results

- `qiki-dev-phase1`: `Up`
- `qiki-operator-console`: `Up (healthy)`
- `qiki-sim-phase1`: `Up (healthy)`
- `qiki-bios-phase1`: `Up (healthy)`
- Pytest slice: `...................................................... [100%]`
- Ruff slice: `All checks passed`
- tmux capture shows `SKELETON/СКЕЛЕТ` block with labeled bars:
  - `Power/EPS: ...`
  - `Thermal: ...`
  - `Comms: ...`
  - `Hull: ...`
  - `Incidents/Инциденты: ...`
- live `F1 quick-actions` smoke:
  - `OK: orion_v_f1_quick_actions_smoke`
  - `POWER_BUTTON=Энергия/Power OK -> F2`
  - `DOCKING_BUTTON=Стыковка/Docking OK -> F2`
  - `COMMS_BUTTON=Связь/Comms WARN -> F2`
  - `QIKI_CONFIRM_READY=QIKI: нет действия/No action`
  - `FINAL_SELECTED_MODULE=docking`
  - `FINAL_QIKI_STATUS=not_sent`

## Checklist Mapping (PASS/FAIL)

1. Mouse selection: PASS  
Evidence: `tests/unit/test_orion_v_app_incidents.py::test_overlay_click_selects_incident`, `::test_status_bars_power_click_opens_f2_and_selects_subsystem`, `::test_status_bars_incidents_click_opens_f3`, `::test_cockpit_power_click_opens_f2_and_selects_power`, `::test_cockpit_qiki_cancel_click_clears_pending_action`.

2. Mouse scroll: PASS  
Evidence: previously validated radar scroll path remains covered in canonical run `ORION_V_CLICKABLE_ACCEPTANCE_RUN_2026-03-01.md`; this run does not regress related routing.

3. Mouse drag: PASS  
Evidence: canonical drag coverage remains in `tests/unit/test_orion_radar_pan_drag.py`; no changes in this slice alter drag pipeline.

4. Keyboard parity: PASS  
Evidence: app bindings/hotkeys unchanged; critical actions still exposed via `BINDINGS` and the temporary command mode in `orion_v/app.py`, while new cockpit quick actions map to existing routes (`F2`, `F3`, `q confirm`, `q cancel`) rather than introducing mouse-only behavior.

5. Degraded environments: PASS  
Evidence: historical tmux runtime proof (`0:%7`, `311x90`) plus headless `run_test` slice at `140x44`. For a fresh replay, resolve the current pane id first and then run the capture command above.

6. No-mocks truth: PASS  
Evidence: status bars use telemetry-derived values and explicit `NODATA` fallback only when values are absent; no fabricated nominal values.

7. Status bars readability (SKELETON/СКЕЛЕТ): PASS  
Evidence: labeled bars visible in runtime tmux capture (`311x90`) and tested behavior at `140x44` through Textual tests (`test_status_bars_hidden_before_telemetry_then_shown`, `test_status_bars_assign_row_status_classes`).

8. F1 quick-actions readability and routing: PASS
Evidence: `bash scripts/prove_orion_v_f1_quick_actions.sh`, artifact `TASKS/ARTIFACT_20260305_orion_v_f1_quick_actions_runtime_proof.md`.
Result: live labels are compact, docking quick action routes to `F2/docking`, QIKI quick actions remain short and cancel path stays on the canonical safe route.

## Verdict

Acceptance run for this profile is PASS.
