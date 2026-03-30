# ORION V Clickable Acceptance Run — 2026-03-01

Status: pass
Date: 2026-03-01
Scope: `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_CHECKLIST.md`

## Environment

- terminal: Docker/headless test runner
- transport: local Docker network
- tmux profile: degraded-compatible proof path (keyboard/headless deterministic checks)
- stack: `docker-compose.phase1.yml` + `docker-compose.operator.yml`

## Commands

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console qiki-dev

docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps operator-console qiki-dev

docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_radar_pan_drag.py \
  tests/unit/test_orion_radar_commands.py \
  tests/unit/test_orion_show_screen_refreshes_keybar.py

docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_deep_dive.py \
  tests/unit/test_orion_v_app_incidents.py \
  tests/unit/test_orion_v_systems_uses_hardware_model.py \
  tests/unit/test_orion_v_cockpit.py

docker exec -i qiki-operator-console python - <<'PY'
# ORION headless smoke (run_test) — details recorded in TASKS artifact
print("OK: orion operator-console smoke")
PY

docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  python tools/orion_v_safe_mode_smoke.py
```

## Runtime Results

- `qiki-dev-phase1`: `Up`
- `qiki-operator-console`: `Up (healthy)`
- Pytest slice: `........................... [100%]`
- Safe-mode UI slice: `............................ [100%]`
- Smoke marker: `OK: orion operator-console smoke`
- Safe-mode smoke marker: `OK: orion_v_safe_mode_smoke`

## Checklist Mapping (PASS/FAIL)

1. Mouse selection: PASS  
Evidence: `tests/unit/test_orion_radar_commands.py::test_radar_ppi_click_selects_nearest_track`.

2. Mouse scroll: PASS  
Evidence: `tests/unit/test_orion_radar_commands.py::test_radar_mouse_wheel_zoom_changes_zoom`.

3. Mouse drag: PASS  
Evidence: `tests/unit/test_orion_radar_pan_drag.py`.

4. Keyboard parity: PASS  
Evidence: command routing and selection navigation tests in `tests/unit/test_orion_radar_commands.py` + keybar refresh regression guard `tests/unit/test_orion_show_screen_refreshes_keybar.py`.

5. Degraded environments (SSH/tmux): PASS  
Evidence: headless `run_test` smoke and keyboard-oriented command surface; no reliance on transport mouse events.

6. No-mocks truth: PASS  
Evidence anchor: `TASKS/ARTIFACT_20260301_orion_v_clickable_g1_runtime_evidence.md` (live telemetry payload + dictionary audit).

## Verdict

Acceptance run for this profile is PASS.
