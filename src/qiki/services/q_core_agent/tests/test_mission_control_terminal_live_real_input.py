from __future__ import annotations

from dataclasses import dataclass

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.mission_control_terminal import MissionControlTerminal
from qiki.services.q_core_agent.core.radar_controls import RadarInputController
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig
from qiki.services.q_core_agent.core.terminal_input_backend import InputEvent


@dataclass
class _FakeBackend:
    name: str
    scripted_events: list[list[InputEvent]]
    close_called: bool = False
    poll_calls: int = 0

    def poll_events(self, timeout_ms: int) -> list[InputEvent]:
        _ = timeout_ms
        self.poll_calls += 1
        if self.scripted_events:
            return self.scripted_events.pop(0)
        return []

    def close(self) -> None:
        self.close_called = True


def _make_terminal(*, fps_max: int = 10) -> MissionControlTerminal:
    terminal = object.__new__(MissionControlTerminal)
    terminal.variant_name = "Test Terminal"
    terminal.event_store = EventStore(maxlen=100, enabled=True)
    terminal.radar_pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=fps_max, color=False)
    )
    terminal.radar_pipeline_error = ""
    terminal.radar_input = RadarInputController()
    terminal.view_state = terminal.radar_pipeline.view_state
    return terminal


def test_live_loop_prefer_real_uses_selected_backend(monkeypatch) -> None:
    terminal = _make_terminal(fps_max=1000)
    backend = _FakeBackend(name="real-terminal", scripted_events=[[InputEvent(kind="key", key="q")]])
    selected: list[bool] = []

    def _fake_select_input_backend(*, prefer_real: bool):
        selected.append(prefer_real)
        return backend, ""

    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.mission_control_terminal.select_input_backend",
        _fake_select_input_backend,
    )
    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.mission_control_terminal.render_terminal_screen",
        lambda events, *, pipeline, view_state: "frame",
    )

    status = terminal.live_radar_loop(prefer_real=True)

    assert status == 0
    assert selected == [True]
    assert backend.close_called is True


def test_live_loop_real_unavailable_falls_back_to_command_mode(monkeypatch, capsys) -> None:
    terminal = _make_terminal()

    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.mission_control_terminal.select_input_backend",
        lambda *, prefer_real: (_FakeBackend(name="line", scripted_events=[]), "unsupported terminal"),
    )

    status = terminal.live_radar_loop(prefer_real=True)

    captured = capsys.readouterr()
    assert status == 3
    assert "staying in command mode" in captured.out.lower()


def test_live_loop_renders_when_input_event_arrives(monkeypatch) -> None:
    terminal = _make_terminal(fps_max=10)
    backend = _FakeBackend(
        name="real-terminal",
        scripted_events=[
            [InputEvent(kind="wheel", delta=1.0)],
            [],
        ],
    )
    rendered: list[str] = []

    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.mission_control_terminal.render_terminal_screen",
        lambda events, *, pipeline, view_state: rendered.append("frame") or "frame",
    )
    monotonic_values = iter([0.0, 0.2, 0.2, 0.4, 0.4, 0.6, 0.6])
    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.mission_control_terminal.time.monotonic",
        lambda: next(monotonic_values),
    )

    status = terminal.live_radar_loop(
        prefer_real=True,
        backend_override=backend,
        max_iterations=2,
    )

    assert status == 0
    assert len(rendered) >= 1
    assert terminal.view_state.zoom > 1.0


def test_live_loop_renders_when_event_store_has_new_events(monkeypatch) -> None:
    terminal = _make_terminal(fps_max=10)
    backend = _FakeBackend(name="real-terminal", scripted_events=[[], [], []])
    rendered: list[str] = []

    def _poll_with_event(timeout_ms: int) -> list[InputEvent]:
        _ = timeout_ms
        backend.poll_calls += 1
        if backend.poll_calls == 2:
            terminal.event_store.append_new(
                subsystem="SENSORS",
                event_type="SENSOR_TRUST_VERDICT",
                payload={"ok": True, "reason": "OK", "data": {"range_m": 5.0, "vr_mps": 0.1}},
                truth_state="OK",
                reason="OK",
            )
        return []

    backend.poll_events = _poll_with_event

    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.mission_control_terminal.render_terminal_screen",
        lambda events, *, pipeline, view_state: rendered.append("frame") or "frame",
    )
    monotonic_values = iter([0.0, 0.2, 0.2, 0.4, 0.4, 0.6, 0.6, 0.8, 0.8])
    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.mission_control_terminal.time.monotonic",
        lambda: next(monotonic_values),
    )

    status = terminal.live_radar_loop(
        prefer_real=True,
        backend_override=backend,
        max_iterations=3,
    )

    assert status == 0
    assert len(rendered) >= 2


def test_live_loop_respects_fps_cap(monkeypatch) -> None:
    terminal = _make_terminal(fps_max=1)
    backend = _FakeBackend(name="real-terminal", scripted_events=[[], [], [], [], []])
    rendered: list[str] = []

    class _Clock:
        def __init__(self) -> None:
            self.now = 0.0

        def __call__(self) -> float:
            self.now += 0.01
            return self.now

    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.mission_control_terminal.time.monotonic",
        _Clock(),
    )
    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.mission_control_terminal.render_terminal_screen",
        lambda events, *, pipeline, view_state: rendered.append("frame") or "frame",
    )

    status = terminal.live_radar_loop(
        prefer_real=True,
        backend_override=backend,
        heartbeat_s=100.0,
        max_iterations=5,
    )

    assert status == 0
    assert len(rendered) == 1


def test_live_loop_exits_on_q() -> None:
    terminal = _make_terminal()
    backend = _FakeBackend(name="real-terminal", scripted_events=[[InputEvent(kind="key", key="q")]])

    status = terminal.live_radar_loop(prefer_real=True, backend_override=backend)

    assert status == 0
