from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.radar_ingestion import Observation
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig
from qiki.services.q_core_agent.core.radar_replay import RadarReplayEngine, load_trace
from qiki.services.q_core_agent.core.trace_export import TraceExportFilter, export_event_store_jsonl_async


def _obs(source: str, track: str, t: float, x: float, y: float, q: float = 0.9) -> Observation:
    return Observation(
        source_id=source,
        t=t,
        track_key=track,
        pos_xy=(x, y),
        vel_xy=(0.2, 0.1),
        quality=q,
    )


def _extract_fusion_signature(store: EventStore) -> list[tuple[str, float]]:
    events = store.filter(subsystem="FUSION", event_type="FUSED_TRACK_UPDATED")
    return [(str(event.payload.get("fused_id", "")), float(event.payload.get("trust", 0.0))) for event in events]


def _extract_situation_sequence(store: EventStore) -> list[tuple[str, str]]:
    events = store.filter(subsystem="SITUATION")
    return [(event.event_type, event.reason) for event in events]


def test_replay_engine_supports_pause_resume_and_jump() -> None:
    events = [
        {"ts": 10.0, "event_type": "A", "payload": {}},
        {"ts": 10.0, "event_type": "B", "payload": {}},
        {"ts": 12.5, "event_type": "C", "payload": {"situation_id": "sit-1"}},
    ]
    engine = RadarReplayEngine(events, speed=2.0, step=False)
    first = engine.next_batch()
    assert [event["event_type"] for event in first] == ["A", "B"]
    engine.pause()
    assert engine.next_batch() == []
    engine.resume()
    assert engine.jump_to_event_type("C") is True
    batch = engine.next_batch()
    assert [event["event_type"] for event in batch] == ["C"]
    engine.jump_to_ts(10.0)
    assert engine.timeline.cursor == 0
    assert engine.jump_to_situation_id("sit-1") is True


def test_pipeline_replay_ignores_live_observations(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    row = {
        "schema_version": 1,
        "ts": 100.0,
        "subsystem": "SENSORS",
        "event_type": "SOURCE_TRACK_UPDATED",
        "truth_state": "OK",
        "reason": "TRACK_UPDATED",
        "session_id": "",
        "payload": {
            "source_id": "replay-radar",
            "source_track_id": "trk-1",
            "t": 100.0,
            "pos": [12.0, 3.0],
            "vel": [0.5, 0.0],
            "quality": 0.8,
            "trust": 0.8,
        },
    }
    trace_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        replay_file=str(trace_path),
    )
    output = pipeline.render_observations(
        [
            _obs(source="live-source", track="live-track", t=101.0, x=999.0, y=999.0, q=0.1),
        ]
    )
    assert output.plan is not None
    assert output.plan.stats.targets_count == 1
    assert pipeline.timeline_state is not None
    assert pipeline.timeline_state.cursor == pipeline.timeline_state.total_events


def test_replay_golden_regression_matches_fusion_and_situations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RADAR_FUSION_ENABLED", "1")
    monkeypatch.setenv("RADAR_FUSION_CONFIRM_FRAMES", "1")
    monkeypatch.setenv("RADAR_FUSION_COOLDOWN_S", "0")

    baseline_store = EventStore(maxlen=500, enabled=True)
    baseline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        event_store=baseline_store,
    )
    base_ts = time.time()
    frames = [
        [_obs("radar-a", "a1", base_ts + 0.0, 10.0, 5.0), _obs("radar-b", "b1", base_ts + 0.0, 10.3, 5.2)],
        [_obs("radar-a", "a1", base_ts + 0.2, 10.1, 5.1), _obs("radar-b", "b1", base_ts + 0.2, 10.4, 5.3)],
        [_obs("radar-a", "a1", base_ts + 0.4, 10.2, 5.2), _obs("radar-b", "b1", base_ts + 0.4, 10.5, 5.4)],
    ]
    for frame in frames:
        baseline.render_observations(frame, truth_state="OK", reason="OK", is_fallback=False)

    trace_path = tmp_path / "baseline_trace.jsonl"
    export_event_store_jsonl_async(
        baseline_store,
        str(trace_path),
        export_filter=TraceExportFilter(types=frozenset({"SOURCE_TRACK_UPDATED"}), max_lines=500),
    )

    replay_store = EventStore(maxlen=500, enabled=True)
    replay = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        event_store=replay_store,
        replay_file=str(trace_path),
    )
    while True:
        state = replay.timeline_state
        if state is None or state.cursor >= state.total_events:
            break
        replay.render_observations([_obs("ignored", "ignored", base_ts, 999.0, 999.0)])

    baseline_fusion = _extract_fusion_signature(baseline_store)
    replay_fusion = _extract_fusion_signature(replay_store)
    assert len(replay_fusion) == len(baseline_fusion)
    for (baseline_id, baseline_trust), (replay_id, replay_trust) in zip(baseline_fusion, replay_fusion, strict=True):
        assert replay_id == baseline_id
        assert replay_trust == pytest.approx(baseline_trust, abs=1e-6)

    assert _extract_situation_sequence(replay_store) == _extract_situation_sequence(baseline_store)


def test_load_trace_sorts_events_by_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    rows = [
        {"ts": 2.0, "event_type": "B", "payload": {}},
        {"ts": 1.0, "event_type": "A", "payload": {}},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    loaded = load_trace(str(path))
    assert [float(item["ts"]) for item in loaded] == [1.0, 2.0]

