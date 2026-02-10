from __future__ import annotations

from qiki.services.q_core_agent.core.mission_control_terminal import MissionControlTerminal
from qiki.services.q_core_agent.core.radar_backends import RadarPoint, RadarScene
from qiki.services.q_core_agent.core.radar_controls import RadarInputController
from qiki.services.q_core_agent.core.radar_view_state import RadarViewState
from qiki.services.q_core_agent.core.terminal_input_backend import (
    InputEvent,
    LineInputBackend,
    RealTerminalInputBackend,
    select_input_backend,
)


def _scene() -> RadarScene:
    return RadarScene(
        ok=True,
        reason="OK",
        truth_state="OK",
        is_fallback=False,
        points=[RadarPoint(x=0.2, y=0.0, z=0.0, metadata={"target_id": "target-1"})],
    )


def test_wheel_event_changes_zoom() -> None:
    controller = RadarInputController()
    state = RadarViewState()
    updated, should_quit = MissionControlTerminal._apply_input_event(
        controller=controller,
        view_state=state,
        event=InputEvent(kind="wheel", delta=1.0),
        scene=_scene(),
    )
    assert should_quit is False
    assert updated.zoom > state.zoom


def test_click_event_updates_selected_target() -> None:
    controller = RadarInputController()
    state = RadarViewState(view="top")
    updated, should_quit = MissionControlTerminal._apply_input_event(
        controller=controller,
        view_state=state,
        event=InputEvent(kind="click", x=0.2, y=0.0),
        scene=_scene(),
    )
    assert should_quit is False
    assert updated.selected_target_id == "target-1"


def test_drag_event_rotates_in_iso() -> None:
    controller = RadarInputController()
    state = RadarViewState(view="iso")
    updated, _ = MissionControlTerminal._apply_input_event(
        controller=controller,
        view_state=state,
        event=InputEvent(kind="drag", dx=0.3, dy=-0.2),
        scene=_scene(),
    )
    assert updated.rot_yaw != state.rot_yaw or updated.rot_pitch != state.rot_pitch


def test_drag_event_pans_in_top() -> None:
    controller = RadarInputController()
    state = RadarViewState(view="top")
    updated, _ = MissionControlTerminal._apply_input_event(
        controller=controller,
        view_state=state,
        event=InputEvent(kind="drag", dx=0.2, dy=-0.2),
        scene=_scene(),
    )
    assert updated.pan_x != state.pan_x or updated.pan_y != state.pan_y


def test_real_backend_unavailable_falls_back_to_line(monkeypatch) -> None:
    monkeypatch.setattr(
        RealTerminalInputBackend,
        "create_or_none",
        classmethod(lambda cls: (None, "unsupported terminal")),
    )
    backend, warning = select_input_backend(prefer_real=True)
    assert isinstance(backend, LineInputBackend)
    assert "fallback to line mode" in warning.lower()

