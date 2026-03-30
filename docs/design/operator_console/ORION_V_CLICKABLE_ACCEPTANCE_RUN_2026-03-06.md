# ORION V Clickable Acceptance Run — 2026-03-06

Status: pass
Date: 2026-03-06
Scope: `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_CHECKLIST.md`

## Why this rebaseline exists

This run revalidates clickable/operability behavior after the live-path contract changed:
- canonical tmux path is now `./scripts/run_orion_v_live.sh`
- `docker attach qiki-operator-console` is no longer accepted as the default interactive path
- ORION V redraw discipline was tightened for navigation, selection, command, replay, and filter UI-state transitions

This run does **not** restart acceptance from zero. It re-proves the changed live-path and redraw-sensitive operator interactions, while keeping earlier unchanged radar scroll/drag evidence as baseline.

## Environment

- terminal: tmux runtime pane + Docker/headless test runner
- transport: local Docker network
- tmux profile: session `1`, window `orionverify`, pane `1:3.0` (`%28`)
- live path: `./scripts/run_orion_v_live.sh`
- pane state during runtime checks: `alternate_on=1`, `mouse_any_flag=1`
- stack: `docker-compose.phase1.yml` + `docker-compose.operator.yml`
- small geometry proof: Textual `run_test` slice at `140x44`

## Commands

```bash
cd /home/sonra44/QIKI_DTMP
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console

docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps operator-console qiki-dev q-sim-service q-bios-service

./scripts/run_orion_v_live.sh

docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_status_bars.py \
  tests/unit/test_orion_v_app_incidents.py \
  tests/unit/test_orion_v_cockpit.py

docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/services/operator_console/orion_v/app.py \
  src/qiki/services/operator_console/orion_v/widgets/status_bars.py \
  src/qiki/services/operator_console/orion_v/screens/cockpit.py \
  tests/unit/test_orion_v_status_bars.py \
  tests/unit/test_orion_v_app_incidents.py \
  tests/unit/test_orion_v_cockpit.py \
  docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_CHECKLIST.md

bash scripts/prove_orion_v_f1_quick_actions.sh
```

## Runtime Results

- `qiki-operator-console`: `Up (healthy)`
- `qiki-sim-phase1`: `Up (healthy)`
- `qiki-bios-phase1`: `Up (healthy)`
- pytest slice: green
- Ruff slice: `All checks passed!`
- live path verification:
  - pane target `1:3.0`
  - pane id `%28`
  - `alternate_on=1`
  - `mouse_any_flag=1`
- command/replay live checks:
  - `/` opens command mode cleanly
  - `Esc` closes command mode cleanly
  - `replay status` works
  - `replay on 60` enters `[АНАЛИЗ]` mode and shows management-disabled banner
  - `replay off` returns cleanly to live `F1`
- `F1 quick-actions` smoke:
  - `OK: orion_v_f1_quick_actions_smoke`
  - `POWER_BUTTON=Энергия/Power OK -> F2`
  - `DOCKING_BUTTON=Стыковка/Docking OK -> F2`
  - `COMMS_BUTTON=Связь/Comms WARN -> F2`
  - `BODY_HAS_PREPARED=1`
  - `FINAL_LEVEL=f1`
  - `FINAL_SELECTED_MODULE=docking`
  - `FINAL_QIKI_STATUS=not_sent`

## Checklist Mapping (PASS/FAIL)

1. Mouse selection: PASS  
Evidence: `tests/unit/test_orion_v_app_incidents.py::test_overlay_click_selects_incident`, `::test_status_bars_power_click_opens_f2_and_selects_subsystem`, `::test_status_bars_incidents_click_opens_f3`, `::test_cockpit_power_click_opens_f2_and_selects_power`, plus live `F1` quick-actions smoke on canonical path.

2. Mouse scroll: PASS  
Evidence: unchanged radar scroll contract remains covered by `ORION_V_CLICKABLE_ACCEPTANCE_RUN_2026-03-01.md`; this rebaseline changed live-path/render discipline, not scroll routing.

3. Mouse drag: PASS  
Evidence: unchanged drag contract remains covered by `tests/unit/test_orion_radar_pan_drag.py`; this rebaseline changed live-path/render discipline, not drag pipeline.

4. Keyboard parity: PASS  
Evidence: command mode remains operational on canonical live path (`/`, `Esc`, replay commands); critical actions still map to existing routes and hotkeys rather than mouse-only flows.

5. Degraded environments: PASS  
Evidence: canonical tmux live path via `./scripts/run_orion_v_live.sh` is now the required path; ORION remains fully operable through keyboard on that path, and no fake “mouse active” hint is introduced.

6. No-mocks truth: PASS  
Evidence: status bars, cockpit quick-actions, replay mode, and `F1` body continue to render payload-backed values and semantic states only; this run introduced no fabricated nominal values.

7. Status bars readability (SKELETON/СКЕЛЕТ): PASS  
Evidence: `tests/unit/test_orion_v_status_bars.py` remains green, including hidden-before-telemetry and status-class behavior; live runtime pane shows readable labeled bars on canonical path.

8. F1 quick-actions readability and routing: PASS  
Evidence: `bash scripts/prove_orion_v_f1_quick_actions.sh`; `F1` quick-actions remain visible and route to the intended detail screens on canonical live path.

## Verdict

Acceptance rebaseline for the canonical tmux live path is PASS.

## Related evidence

- `TASKS/ARTIFACT_20260306_orion_v_live_render_stability_verification.md`
- `TASKS/ARTIFACT_20260305_orion_v_cockpit_clickable_refresh.md`
- `TASKS/ARTIFACT_20260305_orion_v_f1_quick_actions_runtime_proof.md`
- `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_RUN_2026-03-05.md`
- `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_RUN_2026-03-01.md`
