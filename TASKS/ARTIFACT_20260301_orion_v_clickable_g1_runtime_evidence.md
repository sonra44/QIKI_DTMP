# ARTIFACT 2026-03-01 — ORION V Clickable + G1 Runtime Evidence

Status: completed
Date: 2026-03-01
Scope:
- `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_CHECKLIST.md`
- G1 telemetry runtime proof for newly added fields

## Environment

- terminal: Docker exec (`docker compose ... exec -T qiki-dev`)
- tmux: N/A for automated run (headless deterministic tests)
- transport: local Docker network (`nats://nats:4222`)
- project: `/workspace` (container), source repo `/home/sonra44/QIKI_DTMP`

## Reproduction Commands

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build q-sim-service operator-console qiki-dev

docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q \
  tests/unit/test_telemetry_dictionary.py \
  tests/unit/test_orion_radar_pan_drag.py \
  tests/unit/test_orion_radar_commands.py \
  tests/unit/test_orion_show_screen_refreshes_keybar.py

docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  env NATS_URL=nats://nats:4222 python tools/telemetry_smoke.py --audit-dictionary

docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  env NATS_URL=nats://nats:4222 python - <<'PY'
import asyncio, json, nats
async def main():
    nc = await nats.connect('nats://nats:4222')
    fut = asyncio.get_running_loop().create_future()
    async def cb(msg):
        if not fut.done():
            fut.set_result(json.loads(msg.data.decode()))
    sub = await nc.subscribe('qiki.telemetry', cb=cb)
    payload = await asyncio.wait_for(fut, timeout=8)
    view = {
      'schema_version': payload.get('schema_version'),
      'speed_m_s': payload.get('speed_m_s'),
      'velocity': payload.get('velocity'),
      'velocity_xyz_m_s': payload.get('velocity_xyz_m_s'),
      'orbit': payload.get('orbit'),
      'power': {
        'battery_1_voltage_v': (payload.get('power') or {}).get('battery_1_voltage_v'),
        'battery_2_voltage_v': (payload.get('power') or {}).get('battery_2_voltage_v'),
      },
      'comms': {
        'rssi_dbm': (payload.get('comms') or {}).get('rssi_dbm'),
        'snr_db': (payload.get('comms') or {}).get('snr_db'),
        'tx_power_w': (payload.get('comms') or {}).get('tx_power_w'),
        'data_rate_kbps': (payload.get('comms') or {}).get('data_rate_kbps'),
        'antenna_status': (payload.get('comms') or {}).get('antenna_status'),
        'link_state': (payload.get('comms') or {}).get('link_state'),
        'plane_enabled': (payload.get('comms') or {}).get('plane_enabled'),
        'plane_profile': (payload.get('comms') or {}).get('plane_profile'),
        'last_seen_ts': (payload.get('comms') or {}).get('last_seen_ts'),
        'age_s': (payload.get('comms') or {}).get('age_s'),
      },
      'propulsion': {
        'propellant_tank_pressure_pa': (payload.get('propulsion') or {}).get('propellant_tank_pressure_pa'),
        'oxidizer_mass_kg': (payload.get('propulsion') or {}).get('oxidizer_mass_kg'),
      },
    }
    print(json.dumps(view, ensure_ascii=False, sort_keys=True, indent=2))
    await sub.unsubscribe(); await nc.drain(); await nc.close()
asyncio.run(main())
PY
```

## Acceptance Results (Clickable Checklist)

1. Mouse selection: PASS
- Evidence: `tests/unit/test_orion_radar_commands.py::test_radar_ppi_click_selects_nearest_track`
- Result: deterministic track selection by click coordinates.

2. Mouse scroll: PASS
- Evidence: `tests/unit/test_orion_radar_commands.py::test_radar_mouse_wheel_zoom_changes_zoom`
- Result: wheel changes zoom deterministically.

3. Mouse drag: PASS
- Evidence: `tests/unit/test_orion_radar_pan_drag.py`
- Result: drag updates pan and ISO yaw/pitch as expected.

4. Keyboard parity: PASS
- Evidence: `tests/unit/test_orion_radar_commands.py` (`mouse on/off`, command routing, selection navigation paths), plus run of full targeted slice.
- Result: core radar actions remain reachable via keyboard command surface.

5. Degraded environments: PASS (headless parity proof)
- Evidence: deterministic unit tests do not depend on live mouse transport and validate functional parity paths.
- Note: live SSH+tmux profile should be additionally validated in operator session runbook when needed.

6. No-mocks truth: PASS
- Evidence: live `qiki.telemetry` payload + dictionary audit (`tools/telemetry_smoke.py --audit-dictionary`).
- Result: runtime-backed values with semantic state/reason (`orbit.state=off`, reason present).

## Telemetry G1 Payload Evidence (Live)

Observed payload fragment:

```json
{
  "schema_version": 1,
  "speed_m_s": 0.0,
  "velocity": 0.0,
  "velocity_xyz_m_s": {"x": 0.0, "y": 0.0, "z": 0.0},
  "orbit": {
    "state": "off",
    "reason": "insufficient_motion_or_radius",
    "confidence": 0.0,
    "apoapsis_km": null,
    "periapsis_km": null,
    "inclination_deg": 0.0,
    "eccentricity": null,
    "period_min": null
  },
  "power": {
    "battery_1_voltage_v": 28.0,
    "battery_2_voltage_v": 28.0
  },
  "comms": {
    "rssi_dbm": -65.0,
    "snr_db": 24.0,
    "tx_power_w": 6.0,
    "data_rate_kbps": 192.0,
    "antenna_status": "lock",
    "link_state": "online",
    "plane_enabled": true,
    "plane_profile": "ON",
    "last_seen_ts": "2026-03-01T21:11:21.852Z",
    "age_s": 0.0
  },
  "propulsion": {
    "propellant_tank_pressure_pa": 2000000.0,
    "oxidizer_mass_kg": 0.0
  }
}
```

## Audit Output (Live)

- `AUDIT: payload_paths=155 dict_paths=135`
- `OK: received telemetry on qiki.telemetry`
- No `MISSING_IN_PAYLOAD`, no `NOT_IN_DICTIONARY` after dictionary+audit alignment fix.

## Fixes made during evidence run

- `tools/telemetry_smoke.py`:
  - fixed `system` subsystem extraction to include `speed_m_s`, `velocity_xyz_m_s`, `orbit`.
- `docs/design/operator_console/TELEMETRY_DICTIONARY.yaml`:
  - added `comms.link_state`, `comms.plane_enabled`, `comms.plane_profile`, `comms.last_seen_ts`, `comms.age_s`.

## Final verdict

Checklist status: PASS.
G1 payload evidence: PASS.
Remaining gap: optional manual SSH+tmux live operator click session proof (only if explicitly required for release gate).

## Live Docker/tmux-compatible Operator Smoke (2026-03-01)

Environment header:
- terminal: tmux-capable shell environment
- transport: Docker local network
- tmux visual dependency: none (headless `run_test`, deterministic)

Commands:

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml \
  up -d --build --force-recreate operator-console

docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml \
  ps operator-console

docker exec -i qiki-operator-console python - <<'PY'
import asyncio
import time

import qiki.services.operator_console.main_orion as main_orion
from qiki.services.operator_console.radar.unicode_ppi import pick_nearest_track_id


async def _main() -> None:
    async def no_nats(self) -> None:
        self._boot_nats_init_done = True
        self._boot_nats_error = ""
        self.nats_client = None
        self.nats_connected = False

    main_orion.OrionApp._init_nats = no_nats

    app = main_orion.OrionApp()
    now = time.time()
    app._tracks_by_id = {"AAAA": ({"range_m": 100.0, "bearing_deg": 0.0}, now)}

    async with app.run_test(size=(140, 44)) as pilot:
        app.action_show_screen("radar")
        await pilot.pause()

        app._radar_overlay_labels = True
        app._radar_zoom = 1.0
        app._refresh_radar()
        await pilot.pause()

        legend = app.query_one("#radar-legend")
        content = getattr(legend, "content", "")
        plain = content.plain if hasattr(content, "plain") else str(content)
        assert "AAAA" in plain
        assert ("Sel:" in plain) or ("Выбор:" in plain)
        assert "LBL:req" in plain

        app._radar_zoom = 3.0
        app._refresh_radar()
        await pilot.pause()
        content2 = getattr(legend, "content", "")
        plain2 = content2.plain if hasattr(content2, "plain") else str(content2)
        assert "LBL:req" not in plain2
        assert "LBL" in plain2

    width_cells, height_cells = 20, 10
    click_center_x, click_center_y = width_cells // 2, height_cells // 2
    tracks = [("A", {"position": {"x": 0.0, "y": 0.0, "z": 0.0}})]

    picked_low = pick_nearest_track_id(
        tracks,
        click_cell_x=click_center_x + 2,
        click_cell_y=click_center_y,
        width_cells=width_cells,
        height_cells=height_cells,
        max_range_m=1000.0,
        view="top",
        zoom=1.0,
    )
    assert picked_low == "A"

    picked_high = pick_nearest_track_id(
        tracks,
        click_cell_x=click_center_x + 2,
        click_cell_y=click_center_y,
        width_cells=width_cells,
        height_cells=height_cells,
        max_range_m=1000.0,
        view="top",
        zoom=9.0,
    )
    assert picked_high is None


asyncio.run(_main())
print("OK: orion operator-console smoke")
PY
```

Results:
- `operator-console` status: `Up ... (healthy)`
- smoke output: `OK: orion operator-console smoke`
- conclusion: ORION V radar interaction invariants remain valid in live container run, compatible with SSH/tmux degraded profile via keyboard/headless proof path.

Linked run record:
- `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_RUN_2026-03-01.md`

## Continuation Delta (2026-03-01, later loop)

Code/tests added:
- `tests/unit/test_orion_v_cockpit.py`
  - `test_cockpit_motion_block_renders_g1_velocity_and_orbit_fields`
  - `test_cockpit_comms_block_renders_extended_link_metrics`

Purpose:
- lock UI rendering contract for newly introduced G1 fields in cockpit:
  - `speed_m_s`, `velocity_xyz_m_s`, `orbit.*`
  - `comms.snr_db`, `comms.tx_power_w`, `comms.data_rate_kbps`, `comms.antenna_status`

Verification:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_cockpit.py`
  - result: `...... [100%]`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_radar_pan_drag.py tests/unit/test_orion_radar_commands.py tests/unit/test_orion_show_screen_refreshes_keybar.py`
  - result: `................................. [100%]`

## Continuation Delta (2026-03-01, comms module parity)

Code updates:
- `src/qiki/services/operator_console/orion_v/modules/comms.py`
  - summary now falls back `comms.link_state` when `comms.link` is absent;
  - details now consume G1 metrics (`snr_db`, `tx_power_w`, `data_rate_kbps`, `antenna_status`, `age_s`) with legacy fallback for `last_rx_s`;
  - sources-of-truth list extended with new comms keys.

Tests:
- `tests/unit/test_orion_v_subsystem_modules.py`
  - added `test_comms_module_uses_link_state_and_extended_metrics`.

Verification:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_subsystem_modules.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_radar_pan_drag.py tests/unit/test_orion_radar_commands.py tests/unit/test_orion_show_screen_refreshes_keybar.py`
  - result: `.................................... [100%]`

## Continuation Delta (2026-03-01, HWM/F2 comms parity)

Code updates:
- `src/qiki/services/operator_console/orion_v/hardware_view_model/key_aliases.py`
  - added compatibility alias `comms.link -> comms.link_state`;
  - added canonical aliases for `comms.tx_power_w`, `comms.data_rate_kbps`, `comms.antenna_status`;
  - expanded comms subsystem keyset with these fields.
- `src/qiki/services/operator_console/orion_v/hardware_view_model/collector.py`
  - `build_comms` now emits telemetry fields for `tx_power_w`, `data_rate_kbps`, `antenna_status`.
- `src/qiki/services/operator_console/orion_v/screens/systems.py`
  - F2 comms top fields switched to live G1-compatible set:
    - `comms.link_state`, `comms.latency_ms`, `comms.packet_loss_pct`, `comms.snr_db`, `comms.data_rate_kbps`, `comms.age_s`;
  - removed stale `comms.time_without_link_s` from card view.
- `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
  - comms block now falls back to `comms.link_state` when `comms.link` is absent.

Tests added/updated:
- `tests/unit/test_orion_v_hwm_comms_and_aliases.py`
  - `test_alias_map_populates_canonical_keys` now locks `comms.link -> comms.link_state` mapping;
  - added `test_comms_extended_metrics_are_in_hardware_fields`.
- `tests/unit/test_orion_v_cockpit.py`
  - added `test_cockpit_comms_uses_link_state_fallback_when_link_is_missing`.
- `tests/unit/test_orion_v_systems_uses_hardware_model.py`
  - added `test_systems_screen_comms_card_renders_g1_link_metrics`.

Verification:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_hwm_comms_and_aliases.py tests/unit/test_orion_v_systems_uses_hardware_model.py`
  - result: `.................... [100%]`

### Regression Guard Slice (2026-03-01)

Command:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_subsystem_modules.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_hwm_comms_and_aliases.py tests/unit/test_orion_v_systems_uses_hardware_model.py tests/unit/test_orion_radar_pan_drag.py tests/unit/test_orion_radar_commands.py tests/unit/test_orion_show_screen_refreshes_keybar.py`

Result:
- `................................................. [100%]`

Conclusion:
- Expanded comms compatibility (HWM/F2/cockpit) does not regress existing ORION V subsystem/radar interaction slices.

## Continuation Delta (2026-03-01, SAFE MODE authority surface)

Goal:
- close active G1 lock tail for safety authority in ORION V without introducing dual-source in q-sim.

Code updates:
- `src/qiki/services/operator_console/orion_v/app.py`
  - added event-driven `self._safe_mode_state` cache;
  - `_on_event` now updates safe-mode state via `_parse_safe_mode_event(...)`;
  - cockpit receives `safe_mode` state in `set_state(...)`;
  - raw F4 payload now includes `safe_mode` block for observability.
- `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
  - added Safety section (`Безопасность`) with authoritative marker and timestamp;
  - global severity now escalates to CRIT when SAFE MODE is active.

Tests added:
- `tests/unit/test_orion_v_app_incidents.py`
  - `test_parse_safe_mode_event_enter_from_fsm_transition`
  - `test_parse_safe_mode_event_exit_from_safe_mode_signal`
  - `test_on_event_updates_safe_mode_state`
- `tests/unit/test_orion_v_cockpit.py`
  - `test_cockpit_safe_mode_section_is_critical_when_active`
  - `test_cockpit_safe_mode_section_is_ok_when_inactive`

Verification:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_app_incidents.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_hwm_comms_and_aliases.py tests/unit/test_orion_v_systems_uses_hardware_model.py`
  - result: `[100%]`
- broader guard:
  - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_app_incidents.py tests/unit/test_orion_v_subsystem_modules.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_hwm_comms_and_aliases.py tests/unit/test_orion_v_systems_uses_hardware_model.py tests/unit/test_orion_radar_pan_drag.py tests/unit/test_orion_radar_commands.py tests/unit/test_orion_show_screen_refreshes_keybar.py`
  - result: `[100%]`

Live runtime smoke (container):
- `docker ps` status: `qiki-operator-console Up (healthy)`, `qiki-dev-phase1 Up`, `qiki-nats-phase1 Up (healthy)`.
- `docker exec -i qiki-operator-console python ...` (run_test radar smoke) -> `OK: orion operator-console smoke`.

## Continuation Delta (2026-03-01, SAFE MODE propagation F2/F3)

Goal:
- propagate authoritative SAFE MODE signal consistently across ORION V levels (F1 cockpit -> F2 systems -> F3 deep dive), and lock event-to-UI refresh path with a runtime-like test.

Code updates:
- `src/qiki/services/operator_console/orion_v/app.py`
  - F2 `OrionVSystemsScreen.set_state(...)` now receives `safe_mode`.
  - F3 `OrionVDeepDiveScreen.set_state(...)` now receives `safe_mode`.
- `src/qiki/services/operator_console/orion_v/screens/systems.py`
  - added Safety block (`Q-Core authority`) to F2 rendering.
  - added `safe_mode` state handling in `OrionVSystemsScreen`.
- `src/qiki/services/operator_console/orion_v/screens/deep_dive.py`
  - added Safety block (`Q-Core authority`) to F3 rendering.
  - added `safe_mode` state handling in `OrionVDeepDiveScreen`.

Tests added/updated:
- `tests/unit/test_orion_v_app_incidents.py`
  - `test_safe_mode_event_updates_f2_f3_via_refresh_ui` (Textual `run_test`, enter/exit timeline).
- `tests/unit/test_orion_v_systems_uses_hardware_model.py`
  - `test_systems_screen_renders_safe_mode_authority_block`.

Verification:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_app_incidents.py tests/unit/test_orion_v_systems_uses_hardware_model.py tests/unit/test_orion_v_cockpit.py`
  - result: `.......................... [100%]`

Runtime smoke (container, F2/F3 text proof):
- command:
  - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_safe_mode_smoke.py`
- result:
  - `OK: orion_v_safe_mode_smoke`
- covered assertions:
  - F2 (`#orionv-systems`) contains `Безопасность (Q-Core authority):` and `SAFE MODE: ВКЛЮЧЕН/выключен`.
  - F3 (`#orionv-deep`) contains same Safety block and enter/exit reasons.

## Continuation Delta (2026-03-01, F3 text contract hardening)

Goal:
- lock deep-dive (F3) safety rendering at text level to prevent regressions where internal state is updated but operator-visible lines drift.

Code updates:
- `tests/unit/test_orion_v_deep_dive.py` (new):
  - `test_deep_dive_renders_safe_mode_block_active_with_reason`
  - `test_deep_dive_renders_safe_mode_block_without_data`

Verification:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_deep_dive.py tests/unit/test_orion_v_app_incidents.py tests/unit/test_orion_v_systems_uses_hardware_model.py tests/unit/test_orion_v_cockpit.py`
  - result: `............................ [100%]`

### Regression Guard Slice (2026-03-01, extended ORION V)

Command:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_deep_dive.py tests/unit/test_orion_v_app_incidents.py tests/unit/test_orion_v_subsystem_modules.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_hwm_comms_and_aliases.py tests/unit/test_orion_v_systems_uses_hardware_model.py tests/unit/test_orion_radar_pan_drag.py tests/unit/test_orion_radar_commands.py tests/unit/test_orion_show_screen_refreshes_keybar.py`

Result:
- `......................................................`
- `......................... [ 97%]`
- `..                                                                       [100%]`

Conclusion:
- SAFE MODE propagation + F3 rendering hardening do not regress existing ORION V subsystem/radar/navigation interaction slices.
