from __future__ import annotations

import time

import pytest

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.radar_backends.base import RadarScene
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig
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


def _happy_events() -> list[dict]:
    return [
        _event(
            subsystem="FSM",
            event_type="FSM_TRANSITION",
            payload={
                "from_state": "DOCKING_APPROACH",
                "to_state": "DOCKING_APPROACH",
                "trigger_event": "DOCKING_CONFIRMING_1_OF_3",
                "context": {"docking_confirm_hits": 1, "safe_mode_reason": ""},
            },
            reason="DOCKING_CONFIRMING_1_OF_3",
        ),
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
        ),
    ]


def test_forced_unicode_backend_always_selected() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True))
    assert pipeline.active_backend_name == "unicode"


def test_auto_without_bitmap_support_falls_back_to_unicode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.radar_backends.kitty_backend.KittyRadarBackend.is_supported",
        lambda _self: False,
    )
    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.radar_backends.sixel_backend.SixelRadarBackend.is_supported",
        lambda _self: False,
    )
    pipeline = RadarPipeline(RadarRenderConfig(renderer="auto", view="top", fps_max=10, color=True))
    assert pipeline.active_backend_name == "unicode"


def test_forced_kitty_backend_unsupported_fails_fast() -> None:
    with pytest.raises(RuntimeError, match="RADAR_RENDERER=kitty requested"):
        RadarPipeline(RadarRenderConfig(renderer="kitty", view="top", fps_max=10, color=True))


def test_runtime_backend_error_switches_to_unicode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.radar_backends.kitty_backend.KittyRadarBackend.is_supported",
        lambda _self: True,
    )

    def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated render failure")

    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.radar_backends.kitty_backend.KittyRadarBackend.render",
        _boom,
    )

    pipeline = RadarPipeline(RadarRenderConfig(renderer="auto", view="top", fps_max=10, color=True))
    output = pipeline.render_scene(
        RadarScene(ok=False, reason="NO_DATA", truth_state="NO_DATA", is_fallback=False, points=[])
    )
    assert output.backend == "unicode"
    assert output.used_runtime_fallback is True
    assert output.lines[0].startswith("[RADAR RUNTIME FALLBACK kitty->unicode")


def test_no_data_screen_prints_no_data_without_target_markers() -> None:
    events = [
        _event(
            subsystem="SENSORS",
            event_type="SENSOR_TRUST_VERDICT",
            payload={"ok": False, "reason": "NO_DATA", "is_fallback": False, "data": None},
            reason="NO_DATA",
            truth_state="NO_DATA",
        )
    ]
    screen = render_terminal_screen(
        events,
        pipeline=RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True)),
    )
    assert "NO DATA: NO_DATA" in screen
    assert "→" not in screen
    assert "←" not in screen


def test_fallback_sensor_marked_in_hud() -> None:
    events = [
        _event(
            subsystem="SENSORS",
            event_type="SENSOR_TRUST_VERDICT",
            payload={
                "ok": True,
                "reason": "OK",
                "is_fallback": True,
                "data": {"range_m": 4.0, "vr_mps": 0.1},
            },
            reason="OK",
            truth_state="FALLBACK",
        )
    ]
    screen = render_terminal_screen(
        events,
        pipeline=RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True)),
    )
    assert "FALLBACK" in screen


def test_event_log_prints_recent_n_events() -> None:
    events = [
        _event(subsystem="FSM", event_type="FSM_TRANSITION", payload={}, reason="A"),
        _event(subsystem="ACTUATORS", event_type="ACTUATION_RECEIPT", payload={}, reason="B"),
        _event(subsystem="SENSORS", event_type="SENSOR_TRUST_VERDICT", payload={}, reason="C"),
    ]
    screen = render_terminal_screen(
        events,
        event_log_size=2,
        pipeline=RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True)),
    )
    assert "ACTUATION_RECEIPT" in screen
    assert "SENSOR_TRUST_VERDICT" in screen
    assert "FSM_TRANSITION" not in screen


def test_radar_view_changes_projection() -> None:
    events = _happy_events()
    top = render_terminal_screen(
        events,
        pipeline=RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True)),
    )
    side = render_terminal_screen(
        events,
        pipeline=RadarPipeline(RadarRenderConfig(renderer="unicode", view="side", fps_max=10, color=True)),
    )
    assert "view=top" in top
    assert "view=side" in side
    assert top != side


def test_render_tick_telemetry_event_is_written() -> None:
    store = EventStore(maxlen=50, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True),
        event_store=store,
    )
    pipeline.render_scene(RadarScene(ok=False, reason="NO_DATA", truth_state="NO_DATA", is_fallback=False, points=[]))
    ticks = store.filter(subsystem="RADAR", event_type="RADAR_RENDER_TICK")
    assert ticks
    payload = ticks[-1].payload
    expected_keys = (
        "frame_ms",
        "fps_cap",
        "targets_count",
        "lod_level",
        "degradation_level",
        "bitmap_scale",
        "clutter_reasons",
        "backend",
    )
    for key in expected_keys:
        assert key in payload


def test_render_tick_telemetry_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_TELEMETRY", "0")
    store = EventStore(maxlen=50, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True),
        event_store=store,
    )
    pipeline.render_scene(RadarScene(ok=True, reason="OK", truth_state="OK", is_fallback=False, points=[]))
    ticks = store.filter(subsystem="RADAR", event_type="RADAR_RENDER_TICK")
    assert not ticks
