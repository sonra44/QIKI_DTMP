from __future__ import annotations

import time

import pytest

from qiki.services.q_core_agent.core.radar_backends import RadarPoint, RadarScene
from qiki.services.q_core_agent.core.radar_controls import RadarInputController, RadarMouseEvent
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig
from qiki.services.q_core_agent.core.radar_view_state import RadarViewState
from qiki.services.q_core_agent.core.terminal_radar_renderer import render_terminal_screen


def _event(
    *,
    subsystem: str,
    event_type: str,
    payload: dict,
    reason: str,
    truth_state: str = "OK",
) -> dict:
    return {
        "event_id": f"evt-{subsystem}-{event_type}-{int(time.time() * 1000)}",
        "ts": time.time(),
        "subsystem": subsystem,
        "event_type": event_type,
        "payload": payload,
        "tick_id": None,
        "truth_state": truth_state,
        "reason": reason,
    }


def _sensor_ok_events() -> list[dict]:
    return [
        _event(
            subsystem="SENSORS",
            event_type="SENSOR_TRUST_VERDICT",
            payload={
                "ok": True,
                "reason": "OK",
                "is_fallback": False,
                "data": {"range_m": 8.0, "vr_mps": 0.2, "azimuth_deg": 45.0, "elevation_deg": 10.0},
            },
            reason="OK",
            truth_state="OK",
        )
    ]


def test_wheel_up_down_changes_zoom() -> None:
    controller = RadarInputController()
    state = RadarViewState()
    zoomed_in = controller.apply_action(state, controller.handle_mouse(RadarMouseEvent(kind="wheel", delta=1.0)))
    zoomed_out = controller.apply_action(zoomed_in, controller.handle_mouse(RadarMouseEvent(kind="wheel", delta=-1.0)))
    assert zoomed_in.zoom > state.zoom
    assert zoomed_out.zoom < zoomed_in.zoom


def test_drag_changes_pan_in_non_iso() -> None:
    controller = RadarInputController()
    state = RadarViewState(view="top")
    action = controller.handle_mouse(RadarMouseEvent(kind="drag", button="left", is_button_down=True, dx=0.5, dy=-0.25))
    updated = controller.apply_action(state, action)
    assert updated.pan_x != state.pan_x
    assert updated.pan_y != state.pan_y


@pytest.mark.parametrize(
    ("key", "expected"),
    [("1", "top"), ("2", "side"), ("3", "front"), ("4", "iso")],
)
def test_hotkeys_switch_view(key: str, expected: str) -> None:
    controller = RadarInputController()
    updated = controller.apply_key(RadarViewState(view="top"), key)
    assert updated.view == expected


def test_reset_returns_default_view_state() -> None:
    controller = RadarInputController()
    state = RadarViewState(zoom=2.0, pan_x=1.0, pan_y=1.0, rot_yaw=20.0, rot_pitch=10.0, selected_target_id="t-1")
    updated = controller.apply_key(state, "r")
    assert updated.zoom == 1.0
    assert updated.pan_x == 0.0
    assert updated.pan_y == 0.0
    assert updated.rot_yaw == 0.0
    assert updated.rot_pitch == 0.0
    assert updated.selected_target_id is None


def test_toggle_overlays_works() -> None:
    controller = RadarInputController()
    state = RadarViewState(overlays_enabled=True)
    updated = controller.apply_key(state, "o")
    assert updated.overlays_enabled is False


def test_toggle_color_works() -> None:
    controller = RadarInputController()
    state = RadarViewState(color_enabled=True)
    updated = controller.apply_key(state, "c")
    assert updated.color_enabled is False


def test_color_disabled_has_no_ansi_and_has_text_markers() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True))
    events = [
        _event(
            subsystem="SAFE_MODE",
            event_type="SAFE_MODE",
            payload={"action": "hold", "reason": "SENSORS_STALE", "exit_hits": 1, "confirmation_count": 3},
            reason="SENSORS_STALE",
            truth_state="NO_DATA",
        ),
        _event(
            subsystem="SENSORS",
            event_type="SENSOR_TRUST_VERDICT",
            payload={"ok": False, "reason": "NO_DATA", "is_fallback": True, "data": None},
            reason="NO_DATA",
            truth_state="FALLBACK",
        ),
    ]
    screen = render_terminal_screen(events, pipeline=pipeline, view_state=RadarViewState(color_enabled=False))
    assert "\x1b[" not in screen
    assert "[SAFE]" in screen
    assert "FALLBACK" in screen
    assert "[MONO]" in screen


def test_selection_picks_nearest_target() -> None:
    controller = RadarInputController()
    scene = RadarScene(
        ok=True,
        reason="OK",
        truth_state="OK",
        is_fallback=False,
        points=[
            RadarPoint(x=1.0, y=1.0, z=0.0, metadata={"target_id": "near"}),
            RadarPoint(x=8.0, y=8.0, z=0.0, metadata={"target_id": "far"}),
        ],
    )
    action = controller.handle_mouse(RadarMouseEvent(kind="click", x=1.1, y=1.0, button="left"))
    updated = controller.apply_action(RadarViewState(view="top"), action, scene=scene)
    assert updated.selected_target_id == "near"


def test_iso_drag_rotates_angles() -> None:
    controller = RadarInputController()
    state = RadarViewState(view="iso", rot_yaw=0.0, rot_pitch=0.0)
    action = controller.handle_mouse(RadarMouseEvent(kind="drag", button="left", is_button_down=True, dx=1.0, dy=-1.0))
    updated = controller.apply_action(state, action)
    assert updated.rot_yaw != 0.0
    assert updated.rot_pitch != 0.0


def test_missing_mouse_events_are_noop() -> None:
    controller = RadarInputController()
    state = RadarViewState()
    action = controller.handle_mouse(RadarMouseEvent(kind="drag", button="left", is_button_down=False, dx=1.0, dy=1.0))
    updated = controller.apply_action(state, action)
    assert updated == state


def test_render_uses_view_state_view() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))
    events = _sensor_ok_events()
    screen = render_terminal_screen(
        events,
        pipeline=pipeline,
        view_state=RadarViewState(view="iso", color_enabled=False),
    )
    assert "view=iso" in screen
