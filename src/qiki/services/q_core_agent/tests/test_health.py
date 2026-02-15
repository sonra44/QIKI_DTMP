from __future__ import annotations

import time
from pathlib import Path

import pytest

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.health import HealthMonitor, HealthRules
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig


def _base_sections() -> dict[str, dict]:
    return {
        "pipeline": {"frame_ms_avg": 10.0, "frame_ms_p95": 10.0, "fps_est": 100.0, "targets_count": 1},
        "fusion": {"enabled": True, "clusters": 1, "rebuilds_rate": 0.1, "conflict_rate": 0.0, "low_support_rate": 0.0},
        "policy": {"profile": "navigation", "adaptive_level": 0, "degrade_level": 0, "degrade_reasons": []},
        "eventstore": {
            "backend": "memory",
            "sqlite_queue_depth": 0,
            "sqlite_write_lag_ms": 0.0,
            "dropped_events": 0,
            "db_size_mb": 0.0,
        },
        "session": {
            "mode": "standalone",
            "connected_clients": 0,
            "controller_id": "",
            "rtt_ms": 0.0,
            "msgs_per_sec": 0.0,
            "rate_limited_count": 0,
            "stale_ms": 0.0,
        },
        "replay": {"enabled": False, "speed": 1.0, "cursor_ts": 0.0, "lag_ms": 0.0},
    }


def test_health_thresholds_set_overall_status() -> None:
    store = EventStore(maxlen=100, enabled=True)
    monitor = HealthMonitor(
        event_store=store,
        rules=HealthRules(
            frame_p95_warn_ms=30.0,
            frame_p95_crit_ms=60.0,
            sqlite_queue_warn=100,
            sqlite_queue_crit=500,
            session_stale_ms=2_000.0,
            fusion_conflict_warn_rate=0.3,
            strict=False,
        ),
    )
    sections = _base_sections()
    sections["pipeline"]["frame_ms_p95"] = 45.0
    warn = monitor.evaluate(ts=time.time(), **sections)
    assert warn.overall == "WARN"

    sections["pipeline"]["frame_ms_p95"] = 80.0
    crit = monitor.evaluate(ts=time.time(), **sections)
    assert crit.overall == "CRIT"


def test_health_events_are_deduplicated() -> None:
    store = EventStore(maxlen=200, enabled=True)
    monitor = HealthMonitor(
        event_store=store,
        rules=HealthRules(
            frame_p95_warn_ms=20.0,
            frame_p95_crit_ms=40.0,
            sqlite_queue_warn=100,
            sqlite_queue_crit=500,
            session_stale_ms=2_000.0,
            fusion_conflict_warn_rate=0.3,
            strict=False,
        ),
    )
    sections = _base_sections()
    sections["pipeline"]["frame_ms_p95"] = 25.0
    monitor.evaluate(ts=time.time(), **sections)
    monitor.evaluate(ts=time.time(), **sections)
    warns = store.filter(subsystem="HEALTH", event_type="HEALTH_WARN")
    assert len(warns) == 1


def test_pipeline_emits_health_warn_and_crit_for_sqlite_queue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "health.sqlite"
    monkeypatch.setenv("QIKI_HEALTH_SQLITE_QUEUE_WARN", "5")
    monkeypatch.setenv("QIKI_HEALTH_SQLITE_QUEUE_CRIT", "10")
    monkeypatch.setattr(EventStore, "sqlite_queue_depth", property(lambda _self: 12))
    store = EventStore(backend="sqlite", db_path=str(db_path), flush_ms=5, batch_size=10, queue_max=1000)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        event_store=store,
    )
    try:
        pipeline.render_observations([], truth_state="NO_DATA", reason="NO_DATA")
        events = store.filter(subsystem="HEALTH")
        assert any(event.event_type == "HEALTH_CRIT" for event in events)
    finally:
        pipeline.close()


def test_pipeline_emits_no_data_and_recovered_for_session_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_HEALTH_SESSION_STALE_MS", "50")
    store = EventStore(maxlen=500, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        event_store=store,
    )
    try:
        now = time.time()
        pipeline.update_session_health(mode="client", connected_clients=0, last_snapshot_ts=now - 5.0)
        pipeline.render_observations([], truth_state="NO_DATA", reason="NO_DATA")
        no_data_events = store.filter(subsystem="HEALTH", event_type="HEALTH_NO_DATA")
        assert no_data_events

        first_count = len(no_data_events)
        pipeline.render_observations([], truth_state="NO_DATA", reason="NO_DATA")
        assert len(store.filter(subsystem="HEALTH", event_type="HEALTH_NO_DATA")) == first_count

        pipeline.update_session_health(mode="client", connected_clients=1, last_snapshot_ts=time.time())
        pipeline.render_observations([], truth_state="NO_DATA", reason="NO_DATA")
        recovered = store.filter(subsystem="HEALTH", event_type="HEALTH_RECOVERED")
        assert recovered
        assert pipeline.health_snapshot().overall in {"OK", "WARN"}
    finally:
        pipeline.close()

