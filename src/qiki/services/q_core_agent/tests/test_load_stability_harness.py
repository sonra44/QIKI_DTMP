from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from qiki.core.load_harness import run_harness
from qiki.core.load_scenarios import ScenarioConfig, build_scenario
from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.radar_clock import ReplayClock
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline
from qiki.services.q_core_agent.core.trace_export import TraceExportFilter, export_event_store_jsonl_async


def _args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "scenario": "multi_target_300",
        "duration": 5.0,
        "targets": 300,
        "seed": 11,
        "fusion": "on",
        "sqlite": "off",
        "db_path": "artifacts/test_load_harness.sqlite",
        "avg_threshold": 160.0,
        "max_threshold": 700.0,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _run_frames(
    pipeline: RadarPipeline,
    clock: ReplayClock,
    scenario_name: str,
    *,
    seed: int,
    duration_s: float,
    target_count: int,
) -> None:
    frames = build_scenario(
        scenario_name,
        ScenarioConfig(seed=seed, duration_s=duration_s, target_count=target_count),
    )
    for frame in frames:
        clock.set(frame.ts)
        pipeline.render_observations(
            list(frame.observations),
            truth_state=frame.truth_state,
            reason=frame.reason,
            is_fallback=frame.is_fallback,
        )


@pytest.mark.load
def test_load_perf_multi_target_300_thresholds() -> None:
    summary = run_harness(_args(scenario="multi_target_300", duration=6.0, targets=260, sqlite="off"))
    assert summary.frames > 0
    assert summary.avg_frame_ms < 160.0
    assert summary.max_frame_ms < 700.0


@pytest.mark.load
def test_load_fusion_stress_no_fused_id_flapping() -> None:
    store = EventStore(maxlen=200_000, enabled=True, backend="memory")
    clock = ReplayClock(0.0)
    pipeline = RadarPipeline(event_store=store, clock=clock)
    try:
        _run_frames(pipeline, clock, "fusion_conflict", seed=21, duration_s=8.0, target_count=2)
        fused_events = store.filter(subsystem="FUSION", event_type="FUSED_TRACK_UPDATED")
        assert fused_events
        fused_ids = [str(event.payload.get("fused_id", "")) for event in fused_events]
        assert len(set(fused_ids)) <= 6
        perf = pipeline.snapshot_metrics()
        assert perf.fusion_rebuilds == len(fused_events)
    finally:
        store.close()


@pytest.mark.load
def test_load_sqlite_stress_10k_events_no_drop(tmp_path: Path) -> None:
    summary = run_harness(
        _args(
            scenario="high_write_sqlite",
            duration=6.0,
            targets=180,
            sqlite="on",
            db_path=str(tmp_path / "load_stress.sqlite"),
        )
    )
    assert summary.total_events_written >= 10_000
    assert summary.dropped_events == 0


@pytest.mark.load
def test_load_replay_stress_long_trace_deterministic(tmp_path: Path) -> None:
    baseline_store = EventStore(maxlen=300_000, enabled=True, backend="memory")
    baseline_clock = ReplayClock(0.0)
    baseline = RadarPipeline(event_store=baseline_store, clock=baseline_clock)
    trace_path = tmp_path / "task_0030_replay_long.jsonl"

    try:
        _run_frames(
            baseline,
            baseline_clock,
            "replay_long_trace",
            seed=31,
            duration_s=30.0,
            target_count=16,
        )
        rows = baseline_store.stats().rows
        assert rows >= 5_000
        export_event_store_jsonl_async(
            baseline_store,
            str(trace_path),
            export_filter=TraceExportFilter(
                from_ts=0.0,
                to_ts=baseline_clock.now() + 1.0,
                max_lines=200_000,
            ),
            now_ts=baseline_clock.now(),
        )
    finally:
        baseline_store.close()

    replay_store = EventStore(maxlen=300_000, enabled=True, backend="memory")
    try:
        replay = RadarPipeline(event_store=replay_store, replay_file=str(trace_path))
        assert replay.replay_enabled
        for _ in range(1_500):
            replay.render_observations([])
            state = replay.timeline_state
            if state is None or state.cursor >= state.total_events:
                break

        baseline_trace = [
            (event.event_type, str(event.payload.get("track_id", "")))
            for event in [
                json.loads(line)
                for line in trace_path.read_text(encoding="utf-8").splitlines()
            ]
            if event.get("subsystem") == "SITUATION"
        ]
        replay_trace = [
            (event.event_type, str(event.payload.get("track_id", "")))
            for event in replay_store.filter(subsystem="SITUATION")
        ]
        assert replay_trace == baseline_trace

        baseline_fused = [
            str(event.get("payload", {}).get("fused_id", ""))
            for event in [
                json.loads(line)
                for line in trace_path.read_text(encoding="utf-8").splitlines()
            ]
            if event.get("event_type") == "FUSED_TRACK_UPDATED"
        ]
        replay_fused = [
            str(event.payload.get("fused_id", ""))
            for event in replay_store.filter(subsystem="FUSION", event_type="FUSED_TRACK_UPDATED")
        ]
        assert replay_fused == baseline_fused
    finally:
        replay_store.close()
