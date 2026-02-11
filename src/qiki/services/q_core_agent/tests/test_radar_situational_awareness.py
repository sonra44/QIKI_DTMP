from __future__ import annotations

import time

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.radar_backends import RadarPoint, RadarScene
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig
from qiki.services.q_core_agent.core.radar_situation_engine import (
    RadarSituationEngine,
    SituationConfig,
    SituationType,
)
from qiki.services.q_core_agent.core.radar_trail_store import RadarTrailStore
from qiki.services.q_core_agent.core.radar_view_state import RadarViewState


def _point(track_id: str, *, x: float, y: float, z: float, vr: float, **meta: object) -> RadarPoint:
    payload = {"target_id": track_id, **meta}
    return RadarPoint(x=x, y=y, z=z, vr_mps=vr, metadata=payload)


def _scene(points: list[RadarPoint], *, ok: bool = True, truth_state: str = "OK", reason: str = "OK") -> RadarScene:
    return RadarScene(ok=ok, reason=reason, truth_state=truth_state, is_fallback=False, points=points)


def _engine(**overrides: object) -> RadarSituationEngine:
    config = SituationConfig(
        enabled=True,
        cpa_warn_t=20.0,
        cpa_crit_t=8.0,
        cpa_crit_dist=150.0,
        closing_speed_warn=5.0,
        near_dist=300.0,
        near_recent_s=5.0,
        confirm_frames=2,
        cooldown_s=0.2,
        lost_contact_window_s=0.05,
        auto_resolve_after_lost_s=0.05,
    )
    config = SituationConfig(**{**config.__dict__, **overrides})
    return RadarSituationEngine(config=config)


def _eval(engine: RadarSituationEngine, trails: RadarTrailStore, scene: RadarScene):
    trails.update_from_scene(scene)
    return engine.evaluate(scene, trail_store=trails, view_state=RadarViewState(), render_stats=None)


def test_no_data_does_not_create_situations() -> None:
    engine = _engine(confirm_frames=1)
    trails = RadarTrailStore(max_len=5)
    situations, deltas = _eval(engine, trails, _scene([], ok=False, truth_state="NO_DATA", reason="NO_DATA"))
    assert situations == []
    assert deltas == []


def test_lost_contact_emitted_once_after_window() -> None:
    engine = _engine(confirm_frames=1, lost_contact_window_s=0.03)
    trails = RadarTrailStore(max_len=5)
    _eval(engine, trails, _scene([_point("t1", x=90, y=0, z=0, vr=-12)]))
    situations1, deltas1 = _eval(engine, trails, _scene([]))
    assert situations1  # still active before lost window
    assert not any(d.event_type == "situation_lost_contact" for d in deltas1)
    time.sleep(0.04)
    situations2, deltas2 = _eval(engine, trails, _scene([]))
    assert any(d.event_type == "situation_lost_contact" for d in deltas2)
    assert any(s.status.value == "LOST" for s in situations2)
    situations3, deltas3 = _eval(engine, trails, _scene([]))
    assert not any(d.event_type == "situation_lost_contact" for d in deltas3)


def test_auto_resolve_after_lost_without_recovery() -> None:
    engine = _engine(confirm_frames=1, lost_contact_window_s=0.02, auto_resolve_after_lost_s=0.03)
    trails = RadarTrailStore(max_len=5)
    _eval(engine, trails, _scene([_point("t1", x=90, y=0, z=0, vr=-12)]))
    time.sleep(0.03)
    _eval(engine, trails, _scene([]))  # lost
    time.sleep(0.04)
    situations, deltas = _eval(engine, trails, _scene([]))
    assert situations == []
    assert any(d.event_type == "situation_resolved" for d in deltas)


def test_recovery_before_auto_resolve_emits_updated() -> None:
    engine = _engine(confirm_frames=1, lost_contact_window_s=0.02, auto_resolve_after_lost_s=0.2)
    trails = RadarTrailStore(max_len=5)
    _eval(engine, trails, _scene([_point("t1", x=90, y=0, z=0, vr=-12)]))
    time.sleep(0.03)
    _eval(engine, trails, _scene([]))  # lost
    situations, deltas = _eval(engine, trails, _scene([_point("t1", x=92, y=0, z=0, vr=-11)]))
    assert any(s.status.value == "ACTIVE" for s in situations)
    assert any(d.event_type == "situation_updated" and d.situation.reason == "CONTACT_RESTORED" for d in deltas)


def test_confirm_frames_blocks_short_spikes() -> None:
    engine = _engine(confirm_frames=3)
    trails = RadarTrailStore(max_len=10)
    s = _scene([_point("t1", x=90, y=0, z=0, vr=-12)])
    situations1, deltas1 = _eval(engine, trails, s)
    assert situations1 == []
    assert deltas1 == []
    situations2, deltas2 = _eval(engine, trails, s)
    assert situations2 == []
    assert deltas2 == []
    situations3, deltas3 = _eval(engine, trails, s)
    assert any(d.event_type == "situation_created" for d in deltas3)
    assert any(sx.type == SituationType.CPA_RISK for sx in situations3)


def test_cooldown_prevents_immediate_recreate() -> None:
    engine = _engine(confirm_frames=1, cooldown_s=0.2, lost_contact_window_s=0.01, auto_resolve_after_lost_s=0.01)
    trails = RadarTrailStore(max_len=10)
    risky = _scene([_point("t1", x=90, y=0, z=0, vr=-12)])
    _eval(engine, trails, risky)
    time.sleep(0.02)
    _eval(engine, trails, _scene([]))  # lost
    time.sleep(0.02)
    _eval(engine, trails, _scene([]))  # resolved, cooldown starts
    situations, deltas = _eval(engine, trails, risky)
    assert situations == []
    assert not any(d.event_type == "situation_created" for d in deltas)
    time.sleep(0.22)
    situations2, deltas2 = _eval(engine, trails, risky)
    assert any(d.event_type == "situation_created" for d in deltas2)
    assert situations2


def test_closing_fast_detected() -> None:
    engine = _engine(confirm_frames=1)
    trails = RadarTrailStore(max_len=10)
    _eval(engine, trails, _scene([_point("t1", x=300, y=0, z=0, vr=-8)]))
    _eval(engine, trails, _scene([_point("t1", x=250, y=0, z=0, vr=-8)]))
    situations, _ = _eval(engine, trails, _scene([_point("t1", x=200, y=0, z=0, vr=-8)]))
    assert any(s.type == SituationType.CLOSING_FAST for s in situations)


def test_unknown_nearby_detected() -> None:
    engine = _engine(confirm_frames=1)
    trails = RadarTrailStore(max_len=5)
    situations, _ = _eval(
        engine,
        trails,
        _scene([_point("u1", x=120, y=0, z=0, vr=-1, object_type="unknown", age_s=1.0)]),
    )
    assert any(s.type == SituationType.UNKNOWN_NEARBY for s in situations)


def test_eventstore_contract_fields_present() -> None:
    store = EventStore(maxlen=100, enabled=True)
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False), event_store=store)
    pipeline.situation_engine = _engine(confirm_frames=1)
    scene = _scene([_point("t1", x=90, y=0, z=0, vr=-12)])
    pipeline.render_scene(scene)
    events = store.filter(subsystem="SITUATION")
    assert events
    event = events[-1]
    payload = event.payload
    assert event.event_type in {"situation_created", "situation_updated", "situation_resolved", "situation_lost_contact"}
    assert isinstance(payload.get("timestamp"), float)
    assert isinstance(payload.get("session_id"), str)
    assert isinstance(payload.get("track_id"), str)
    assert isinstance(payload.get("situation_id"), str)
    assert payload.get("severity") in {"INFO", "WARN", "CRITICAL"}
    assert isinstance(event.reason, str) and event.reason
    metrics = payload.get("metrics")
    assert isinstance(metrics, dict)


def test_pipeline_writes_lost_contact_and_resolved_events() -> None:
    store = EventStore(maxlen=200, enabled=True)
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False), event_store=store)
    pipeline.situation_engine = _engine(confirm_frames=1, lost_contact_window_s=0.02, auto_resolve_after_lost_s=0.02)
    pipeline.render_scene(_scene([_point("t1", x=90, y=0, z=0, vr=-12)]))
    time.sleep(0.03)
    pipeline.render_scene(_scene([]))
    time.sleep(0.03)
    pipeline.render_scene(_scene([]))
    etypes = [e.event_type for e in store.filter(subsystem="SITUATION")]
    assert "situation_lost_contact" in etypes
    assert "situation_resolved" in etypes


def test_no_data_does_not_create_new_eventstore_situations() -> None:
    store = EventStore(maxlen=50, enabled=True)
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False), event_store=store)
    pipeline.situation_engine = _engine(confirm_frames=1)
    pipeline.render_scene(_scene([], ok=False, truth_state="NO_DATA", reason="NO_DATA"))
    assert store.filter(subsystem="SITUATION") == []


def test_integration_sequence_expected_event_order() -> None:
    store = EventStore(maxlen=400, enabled=True)
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False), event_store=store)
    pipeline.situation_engine = _engine(confirm_frames=2, lost_contact_window_s=0.02, auto_resolve_after_lost_s=0.03, cooldown_s=0.05)

    # normal frames -> create
    pipeline.render_scene(_scene([_point("t1", x=90, y=0, z=0, vr=-12)]))
    pipeline.render_scene(_scene([_point("t1", x=89, y=0, z=0, vr=-12)]))

    # data drop -> lost -> resolve
    time.sleep(0.03)
    pipeline.render_scene(_scene([]))
    time.sleep(0.04)
    pipeline.render_scene(_scene([]))

    # oscillation around threshold shorter than confirm should not recreate immediately
    pipeline.render_scene(_scene([_point("t1", x=800, y=0, z=0, vr=-1)]))
    pipeline.render_scene(_scene([_point("t1", x=90, y=0, z=0, vr=-12)]))

    event_types = [e.event_type for e in store.filter(subsystem="SITUATION")]
    assert "situation_created" in event_types
    assert "situation_lost_contact" in event_types
    assert "situation_resolved" in event_types


def test_performance_smoke_no_event_spam_on_flapping() -> None:
    store = EventStore(maxlen=2000, enabled=True)
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False), event_store=store)
    pipeline.situation_engine = _engine(confirm_frames=3, cooldown_s=0.2)
    for i in range(40):
        if i % 2 == 0:
            pipeline.render_scene(_scene([_point("t1", x=92, y=0, z=0, vr=-12)]))
        else:
            pipeline.render_scene(_scene([_point("t1", x=900, y=0, z=0, vr=2)]))
    situation_events = store.filter(subsystem="SITUATION")
    assert len(situation_events) < 20
