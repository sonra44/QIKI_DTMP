from __future__ import annotations

import json
import time

import pytest

from qiki.services.q_core_agent.core.event_store import EventStore, SystemEvent, TruthState
from qiki.services.q_core_agent.core.radar_ingestion import Observation
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig
from qiki.services.q_core_agent.core.trace_export import (
    TraceExportFilter,
    build_export_envelope,
    export_event_store_jsonl_async,
)


def test_trace_export_envelope_stable_and_payload_preserved() -> None:
    payload = {"session_id": "sess-1", "value": 42, "nested": {"ok": True}}
    event = SystemEvent(
        event_id="evt-1",
        ts=1234.5,
        subsystem="RADAR",
        event_type="RADAR_RENDER_TICK",
        payload=payload,
        tick_id=None,
        truth_state=TruthState.OK,
        reason="OK",
    )

    row = build_export_envelope(event)

    assert set(row.keys()) == {
        "schema_version",
        "ts",
        "subsystem",
        "event_type",
        "truth_state",
        "reason",
        "payload",
        "session_id",
    }
    assert row["schema_version"] == 1
    assert row["payload"] == payload
    assert row["session_id"] == "sess-1"
    assert row["truth_state"] == "OK"


def test_trace_export_filters_and_types_subsystems_truth(tmp_path) -> None:
    store = EventStore(maxlen=50, enabled=True)
    now = time.time()
    store.append(
        SystemEvent(
            event_id="e1",
            ts=now - 10.0,
            subsystem="RADAR",
            event_type="RADAR_RENDER_TICK",
            payload={},
            tick_id=None,
            truth_state=TruthState.OK,
            reason="OK",
        )
    )
    store.append(
        SystemEvent(
            event_id="e2",
            ts=now - 5.0,
            subsystem="FUSION",
            event_type="FUSED_TRACK_UPDATED",
            payload={},
            tick_id=None,
            truth_state=TruthState.OK,
            reason="TRACK_FUSED",
        )
    )
    store.append(
        SystemEvent(
            event_id="e3",
            ts=now - 1.0,
            subsystem="SITUATION",
            event_type="SITUATION_UPDATED",
            payload={},
            tick_id=None,
            truth_state=TruthState.NO_DATA,
            reason="NO_DATA",
        )
    )

    out_path = tmp_path / "trace.jsonl"
    result = export_event_store_jsonl_async(
        store,
        str(out_path),
        export_filter=TraceExportFilter(
            from_ts=now - 6.0,
            to_ts=now,
            types=frozenset({"FUSED_TRACK_UPDATED"}),
            subsystems=frozenset({"FUSION"}),
            truth_states=frozenset({"OK"}),
            max_lines=100,
        ),
        now_ts=now,
    )
    assert result.lines_written == 1
    rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["subsystem"] == "FUSION"
    assert rows[0]["event_type"] == "FUSED_TRACK_UPDATED"


def test_trace_export_max_lines_limit(tmp_path) -> None:
    store = EventStore(maxlen=100, enabled=True)
    for idx in range(10):
        store.append_new(
            subsystem="RADAR",
            event_type="RADAR_RENDER_TICK",
            payload={"i": idx},
            truth_state=TruthState.OK,
            reason="OK",
        )
    out_path = tmp_path / "limited.jsonl"
    result = export_event_store_jsonl_async(
        store,
        str(out_path),
        export_filter=TraceExportFilter(max_lines=3),
    )
    assert result.lines_written == 3
    assert len(out_path.read_text(encoding="utf-8").splitlines()) == 3


def test_trace_export_emits_started_and_finished_events(tmp_path) -> None:
    store = EventStore(maxlen=100, enabled=True)
    store.append_new(
        subsystem="RADAR",
        event_type="RADAR_RENDER_TICK",
        payload={"frame_ms": 1.0},
        truth_state=TruthState.OK,
        reason="OK",
    )
    out_path = tmp_path / "trace_events.jsonl"
    export_event_store_jsonl_async(store, str(out_path))
    started = store.filter(subsystem="TRACE", event_type="TRACE_EXPORT_STARTED")
    finished = store.filter(subsystem="TRACE", event_type="TRACE_EXPORT_FINISHED")
    assert started
    assert finished
    assert finished[-1].payload["lines_written"] >= 1
    assert finished[-1].payload["error"] == ""


def test_trace_export_failed_event_on_writer_error(tmp_path, monkeypatch) -> None:
    store = EventStore(maxlen=100, enabled=True)
    store.append_new(subsystem="RADAR", event_type="RADAR_RENDER_TICK", payload={}, reason="OK")

    def _boom(_self):
        raise RuntimeError("writer-failed")

    monkeypatch.setattr("qiki.services.q_core_agent.core.trace_export._AsyncJsonlWriter.finish", _boom)
    out_path = tmp_path / "will_fail.jsonl"
    with pytest.raises(RuntimeError, match="writer-failed"):
        export_event_store_jsonl_async(store, str(out_path))

    failed = store.filter(subsystem="TRACE", event_type="TRACE_EXPORT_FAILED")
    assert failed
    assert "writer-failed" in failed[-1].payload["error"]


def test_trace_export_integration_with_pipeline(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RADAR_FUSION_ENABLED", "1")
    store = EventStore(maxlen=500, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True),
        event_store=store,
    )
    for idx in range(3):
        observations = [
            Observation(
                source_id="radar-a",
                t=100.0 + float(idx),
                track_key="target-1",
                pos_xy=(100.0, 10.0),
                vel_xy=(0.5, -0.1),
                quality=0.9,
            ),
            Observation(
                source_id="radar-b",
                t=100.0 + float(idx),
                track_key="target-1b",
                pos_xy=(101.0, 10.5),
                vel_xy=(0.45, -0.15),
                quality=0.85,
            ),
        ]
        pipeline.render_observations(observations, truth_state="OK", reason="OK", is_fallback=False)
    store.append_new(
        subsystem="SITUATION",
        event_type="SITUATION_UPDATED",
        payload={"session_id": pipeline.session_id, "severity": "WARN", "reason": "CPA_RISK"},
        truth_state=TruthState.OK,
        reason="CPA_RISK",
    )

    out_path = tmp_path / "pipeline_trace.jsonl"
    now = time.time()
    result = export_event_store_jsonl_async(
        store,
        str(out_path),
        export_filter=TraceExportFilter(
            from_ts=now - 120.0,
            to_ts=now + 120.0,
            types=frozenset({"RADAR_RENDER_TICK", "FUSED_TRACK_UPDATED", "SITUATION_UPDATED"}),
            max_lines=200,
        ),
    )
    assert result.lines_written >= 3
    rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
    assert rows
    assert any(row["event_type"] == "RADAR_RENDER_TICK" for row in rows)
    assert any(row["event_type"] == "FUSED_TRACK_UPDATED" for row in rows)
    assert any(row["event_type"] == "SITUATION_UPDATED" for row in rows)
