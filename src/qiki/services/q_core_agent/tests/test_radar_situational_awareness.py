from __future__ import annotations

import time
from dataclasses import replace

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.radar_backends import RadarPoint, RadarScene
from qiki.services.q_core_agent.core.radar_controls import RadarInputController
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig
from qiki.services.q_core_agent.core.radar_situation_engine import (
    RadarSituationEngine,
    Situation,
    SituationConfig,
    SituationSeverity,
    SituationType,
)
from qiki.services.q_core_agent.core.radar_trail_store import RadarTrailStore
from qiki.services.q_core_agent.core.radar_view_state import RadarInspectorState, RadarViewState
from qiki.services.q_core_agent.core.terminal_radar_renderer import render_terminal_screen


def _point(track_id: str, *, x: float, y: float, z: float, vr: float, **meta: object) -> RadarPoint:
    payload = {"target_id": track_id, **meta}
    return RadarPoint(x=x, y=y, z=z, vr_mps=vr, metadata=payload)


def _scene(points: list[RadarPoint], *, ok: bool = True, truth_state: str = "OK", reason: str = "OK") -> RadarScene:
    return RadarScene(ok=ok, reason=reason, truth_state=truth_state, is_fallback=False, points=points)


def _engine() -> RadarSituationEngine:
    config = SituationConfig(
        enabled=True,
        cpa_warn_t=20.0,
        cpa_crit_t=8.0,
        cpa_crit_dist=150.0,
        closing_speed_warn=5.0,
        near_dist=300.0,
        near_recent_s=5.0,
        closing_confirm_frames=3,
        lost_contact_recent_s=10.0,
    )
    return RadarSituationEngine(config=config)


def test_cpa_warn_is_created() -> None:
    engine = _engine()
    trails = RadarTrailStore(max_len=5)
    scene = _scene([_point("t1", x=400.0, y=0.0, z=0.0, vr=-25.0)])
    trails.update_from_scene(scene)
    situations, _ = engine.evaluate(scene, trail_store=trails, view_state=RadarViewState(), render_stats=None)
    assert any(s.type == SituationType.CPA_RISK and s.severity == SituationSeverity.WARN for s in situations)


def test_cpa_critical_is_created() -> None:
    engine = _engine()
    trails = RadarTrailStore(max_len=5)
    scene = _scene([_point("t1", x=90.0, y=0.0, z=0.0, vr=-20.0)])
    trails.update_from_scene(scene)
    situations, _ = engine.evaluate(scene, trail_store=trails, view_state=RadarViewState(), render_stats=None)
    assert any(s.type == SituationType.CPA_RISK and s.severity == SituationSeverity.CRITICAL for s in situations)


def test_cpa_resolved_emits_resolved_delta() -> None:
    engine = _engine()
    trails = RadarTrailStore(max_len=5)
    risky = _scene([_point("t1", x=90.0, y=0.0, z=0.0, vr=-20.0)])
    trails.update_from_scene(risky)
    engine.evaluate(risky, trail_store=trails, view_state=RadarViewState(), render_stats=None)

    safe = _scene([_point("t1", x=900.0, y=0.0, z=0.0, vr=2.0)])
    trails.update_from_scene(safe)
    _, deltas = engine.evaluate(safe, trail_store=trails, view_state=RadarViewState(), render_stats=None)
    assert any(delta.event_type == "SITUATION_RESOLVED" and delta.situation.type == SituationType.CPA_RISK for delta in deltas)


def test_closing_fast_warn_is_created() -> None:
    engine = _engine()
    trails = RadarTrailStore(max_len=10)
    for distance in (300.0, 250.0, 200.0):
        frame = _scene([_point("t1", x=distance, y=0.0, z=0.0, vr=-8.0)])
        trails.update_from_scene(frame)
    situations, _ = engine.evaluate(frame, trail_store=trails, view_state=RadarViewState(), render_stats=None)
    assert any(s.type == SituationType.CLOSING_FAST for s in situations)


def test_unknown_nearby_warn_is_created() -> None:
    engine = _engine()
    trails = RadarTrailStore(max_len=5)
    scene = _scene([_point("unk", x=100.0, y=0.0, z=0.0, vr=-1.0, object_type="unknown", age_s=1.0)])
    trails.update_from_scene(scene)
    situations, _ = engine.evaluate(scene, trail_store=trails, view_state=RadarViewState(), render_stats=None)
    assert any(s.type == SituationType.UNKNOWN_NEARBY for s in situations)


def test_lost_contact_warn_is_created() -> None:
    engine = _engine()
    trails = RadarTrailStore(max_len=5)
    first = _scene([_point("t1", x=120.0, y=0.0, z=0.0, vr=-2.0)])
    trails.update_from_scene(first)
    engine.evaluate(first, trail_store=trails, view_state=RadarViewState(), render_stats=None)
    second = _scene([])
    trails.update_from_scene(second)
    situations, _ = engine.evaluate(second, trail_store=trails, view_state=RadarViewState(), render_stats=None)
    assert any(s.type == SituationType.LOST_CONTACT for s in situations)


def test_critical_alert_overlay_visible_on_scene() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False), event_store=EventStore())
    scene = _scene([_point("t1", x=90.0, y=0.0, z=0.0, vr=-20.0)])
    out = pipeline.render_scene(scene, view_state=RadarViewState())
    joined = "\n".join(out.lines)
    assert "✶" in joined or ":" in joined


def test_info_alert_is_not_drawn_on_scene() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False), event_store=EventStore())

    info = Situation(
        id="manual-info",
        type=SituationType.ZONE_VIOLATION,
        severity=SituationSeverity.INFO,
        track_ids=("t1",),
        metrics={},
        created_ts=time.time(),
        last_update_ts=time.time(),
        is_active=True,
    )

    def _fake_eval(*_args, **_kwargs):
        return [info], []

    pipeline.situation_engine.evaluate = _fake_eval  # type: ignore[assignment]
    scene = _scene([_point("t1", x=200.0, y=0.0, z=0.0, vr=-1.0)])
    out = pipeline.render_scene(scene, view_state=RadarViewState())
    joined = "\n".join(out.lines)
    assert "✶" not in joined


def test_inspector_shows_selected_situations() -> None:
    events = [
        {
            "event_id": "e1",
            "ts": time.time(),
            "subsystem": "SENSORS",
            "event_type": "SENSOR_TRUST_VERDICT",
            "payload": {
                "ok": True,
                "reason": "OK",
                "is_fallback": False,
                "data": {"tracks": [{"track_id": "t1", "range_m": 120.0, "vr_mps": -10.0}]},
            },
            "truth_state": "OK",
            "reason": "OK",
        }
    ]
    view_state = RadarViewState(inspector=RadarInspectorState(mode="on"), selected_target_id="t1")
    screen = render_terminal_screen(events, pipeline=RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False)), view_state=view_state)
    assert "INSPECTOR:" in screen
    assert "situation=" in screen


def test_inspector_empty_when_no_situations() -> None:
    events = [
        {
            "event_id": "e1",
            "ts": time.time(),
            "subsystem": "SENSORS",
            "event_type": "SENSOR_TRUST_VERDICT",
            "payload": {"ok": False, "reason": "NO_DATA", "is_fallback": False, "data": None},
            "truth_state": "NO_DATA",
            "reason": "NO_DATA",
        }
    ]
    view_state = RadarViewState(inspector=RadarInspectorState(mode="on"), selected_target_id="t1")
    screen = render_terminal_screen(
        events,
        pipeline=RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False)),
        view_state=view_state,
    )
    assert "situation=none" in screen or "no selection" in screen or "not found" in screen


def test_hud_counts_alert_severity() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False), event_store=EventStore())
    scene = _scene(
        [
            _point("crit", x=90.0, y=0.0, z=0.0, vr=-20.0),
            _point("warn", x=100.0, y=0.0, z=0.0, vr=-6.0, object_type="unknown", age_s=1.0),
        ]
    )
    out = pipeline.render_scene(scene)
    events = []
    for idx, situation in enumerate(pipeline.last_situations):
        events.append(
            {
                "event_id": f"sx-{idx}",
                "ts": time.time(),
                "subsystem": "SITUATION",
                "event_type": "SITUATION_CREATED",
                "payload": {
                    "type": situation.type.value,
                    "severity": situation.severity.value,
                    "track_ids": list(situation.track_ids),
                },
                "truth_state": "OK",
                "reason": situation.type.value,
            }
        )
    screen = render_terminal_screen(events, pipeline=pipeline)
    assert "ALERTS:" in screen


def test_cycle_alerts_switches_selection() -> None:
    controller = RadarInputController()
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False), event_store=EventStore())
    scene = _scene(
        [
            _point("a", x=90.0, y=0.0, z=0.0, vr=-20.0),
            _point("b", x=120.0, y=0.0, z=0.0, vr=-15.0),
        ]
    )
    state = RadarViewState()
    out1 = pipeline.render_scene(scene, view_state=state)
    selected1 = pipeline._apply_alert_selection(state, list(pipeline.last_situations)).selected_target_id
    state2 = controller.apply_key(state, "j")
    out2 = pipeline.render_scene(scene, view_state=state2)
    selected2 = pipeline._apply_alert_selection(state2, list(pipeline.last_situations)).selected_target_id
    assert selected1 != selected2


def test_toggle_situations_overlays_off() -> None:
    controller = RadarInputController()
    state = controller.apply_key(RadarViewState(), "s")
    assert state.alerts.situations_enabled is False


def test_no_data_does_not_generate_new_situations() -> None:
    engine = _engine()
    trails = RadarTrailStore(max_len=5)
    scene = _scene([], ok=False, truth_state="NO_DATA", reason="NO_DATA")
    situations, deltas = engine.evaluate(scene, trail_store=trails, view_state=RadarViewState(), render_stats=None)
    assert situations == []
    assert deltas == []


def test_fallback_marked_in_inspector() -> None:
    events = [
        {
            "event_id": "e1",
            "ts": time.time(),
            "subsystem": "SENSORS",
            "event_type": "SENSOR_TRUST_VERDICT",
            "payload": {
                "ok": True,
                "reason": "OK",
                "is_fallback": True,
                "data": {"tracks": [{"track_id": "t1", "range_m": 20.0, "vr_mps": -1.0}]},
            },
            "truth_state": "FALLBACK",
            "reason": "OK",
        }
    ]
    screen = render_terminal_screen(
        events,
        pipeline=RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False)),
        view_state=RadarViewState(inspector=RadarInspectorState(mode="on"), selected_target_id="t1"),
    )
    assert "FALLBACK" in screen


def test_lod_and_clutter_still_available() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False), event_store=EventStore())
    scene = _scene([_point(f"t{i}", x=100.0 + i, y=float(i), z=0.0, vr=-1.0) for i in range(60)])
    out = pipeline.render_scene(scene)
    assert out.plan is not None
    assert out.stats is not None
    assert out.plan.lod_level >= 0


def test_backends_receive_render_plan_consistently() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False), event_store=EventStore())
    scene = _scene([_point("t1", x=120.0, y=20.0, z=0.0, vr=-2.0)])
    out = pipeline.render_scene(scene)
    assert out.plan is not None
    assert out.stats is out.plan.stats


def test_situation_events_written_to_event_store() -> None:
    store = EventStore(maxlen=100, enabled=True)
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False), event_store=store)
    scene = _scene([_point("t1", x=90.0, y=0.0, z=0.0, vr=-20.0)])
    pipeline.render_scene(scene)
    events = store.filter(subsystem="SITUATION")
    assert events
    assert events[-1].event_type in {"SITUATION_CREATED", "SITUATION_UPDATED"}


def test_toggle_overlay_hides_situation_marker() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False), event_store=EventStore())
    scene = _scene([_point("t1", x=90.0, y=0.0, z=0.0, vr=-20.0)])
    on_state = RadarViewState()
    off_state = replace(RadarViewState(), alerts=replace(RadarViewState().alerts, situations_enabled=False))
    on = "\n".join(pipeline.render_scene(scene, view_state=on_state).lines)
    off = "\n".join(pipeline.render_scene(scene, view_state=off_state).lines)
    assert ("✶" in on or ":" in on) and ("✶" not in off)
