from __future__ import annotations

import json
import time
from pathlib import Path

from qiki.services.q_core_agent.core.event_store import EventStore, TruthState
from qiki.services.q_core_agent.core.radar_ingestion import Observation
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig
from qiki.services.q_core_agent.core.trace_export import TraceExportFilter, export_event_store_jsonl_async


def _obs(source: str, track: str, t: float, x: float, y: float) -> Observation:
    return Observation(
        source_id=source,
        t=t,
        track_key=track,
        pos_xy=(x, y),
        vel_xy=(0.2, 0.1),
        quality=0.9,
    )


def test_sqlite_eventstore_roundtrip_and_payload_integrity(tmp_path: Path) -> None:
    db_path = tmp_path / "events.sqlite"
    store = EventStore(
        maxlen=100,
        enabled=True,
        backend="sqlite",
        db_path=str(db_path),
        flush_ms=5,
        batch_size=10,
        queue_max=1000,
    )
    payload = {"session_id": "sess-1", "value": 42, "nested": {"ok": True}}
    store.append_new(
        subsystem="TRACE",
        event_type="ROUNDTRIP",
        payload=payload,
        truth_state=TruthState.OK,
        reason="OK",
    )
    rows = store.query(from_ts=0.0, to_ts=time.time() + 5.0, types={"ROUNDTRIP"}, order="asc")
    assert rows
    assert rows[-1].payload == payload
    store.close()


def test_sqlite_query_filters_by_time_type_subsystem_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "events.sqlite"
    store = EventStore(backend="sqlite", db_path=str(db_path), flush_ms=5, batch_size=10, queue_max=1000)
    now = time.time()
    store.append_new(subsystem="RADAR", event_type="A", payload={}, ts=now - 5.0)
    store.append_new(subsystem="FUSION", event_type="B", payload={}, ts=now - 3.0)
    store.append_new(subsystem="RADAR", event_type="C", payload={}, ts=now - 1.0)

    rows = store.query(
        from_ts=now - 4.0,
        to_ts=now,
        types={"B", "C"},
        subsystems={"FUSION", "RADAR"},
        limit=1,
        order="asc",
    )
    assert len(rows) == 1
    assert rows[0].event_type == "B"
    store.close()


def test_sqlite_retention_deletes_old_events(tmp_path: Path) -> None:
    db_path = tmp_path / "events.sqlite"
    now = time.time()
    store = EventStore(
        backend="sqlite",
        db_path=str(db_path),
        flush_ms=5,
        batch_size=10,
        queue_max=1000,
        retention_hours=1.0 / 3600.0,
        max_db_mb=64.0,
    )
    store.append_new(subsystem="RET", event_type="OLD", payload={}, ts=now - 120.0)
    # Force retention pass via append with current timestamp.
    store.append_new(subsystem="RET", event_type="NEW", payload={}, ts=now)
    rows = store.query(from_ts=0.0, to_ts=now + 1.0, types={"OLD", "NEW"}, order="asc")
    assert any(row.event_type == "NEW" for row in rows)
    assert all(row.event_type != "OLD" for row in rows)
    store.close()


def test_sqlite_close_flushes_all_queued_events(tmp_path: Path) -> None:
    db_path = tmp_path / "flush.sqlite"
    store = EventStore(
        backend="sqlite",
        db_path=str(db_path),
        flush_ms=200,
        batch_size=1000,
        queue_max=10_000,
    )
    total = 500
    for idx in range(total):
        store.append_new(
            subsystem="FLUSH",
            event_type="ITEM",
            payload={"idx": idx},
            ts=time.time(),
        )
    store.close()
    reopened = EventStore(
        backend="sqlite",
        db_path=str(db_path),
        flush_ms=5,
        batch_size=100,
        queue_max=1000,
    )
    rows = reopened.query(from_ts=0.0, to_ts=time.time() + 5.0, types={"ITEM"}, subsystems={"FLUSH"}, order="asc")
    assert len(rows) == total
    reopened.close()


def test_pipeline_writes_events_into_sqlite(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RADAR_FUSION_ENABLED", "1")
    db_path = tmp_path / "pipeline.sqlite"
    store = EventStore(backend="sqlite", db_path=str(db_path), flush_ms=5, batch_size=10, queue_max=1000)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        event_store=store,
    )
    pipeline.render_observations([_obs("a", "t1", time.time(), 10.0, 3.0)], truth_state="OK", reason="OK")
    rows = store.query(from_ts=0.0, to_ts=time.time() + 2.0, types={"RADAR_RENDER_TICK"}, order="asc")
    assert rows
    store.close()


def test_trace_export_reads_from_sqlite_backend(tmp_path: Path) -> None:
    db_path = tmp_path / "trace.sqlite"
    store = EventStore(backend="sqlite", db_path=str(db_path), flush_ms=5, batch_size=10, queue_max=1000)
    now = time.time()
    store.append_new(subsystem="RADAR", event_type="RADAR_RENDER_TICK", payload={"frame_ms": 1.0}, ts=now - 1.0)
    store.append_new(subsystem="FUSION", event_type="FUSED_TRACK_UPDATED", payload={"fused_id": "f1"}, ts=now)
    out_path = tmp_path / "trace.jsonl"
    result = export_event_store_jsonl_async(
        store,
        str(out_path),
        export_filter=TraceExportFilter(
            from_ts=now - 2.0,
            to_ts=now + 1.0,
            types=frozenset({"FUSED_TRACK_UPDATED"}),
            max_lines=100,
        ),
    )
    assert result.lines_written == 1
    rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["event_type"] == "FUSED_TRACK_UPDATED"
    store.close()


def test_replay_from_sqlite_db(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "replay.sqlite"
    store = EventStore(backend="sqlite", db_path=str(db_path), flush_ms=5, batch_size=10, queue_max=1000)
    now = time.time()
    store.append_new(
        subsystem="SENSORS",
        event_type="SOURCE_TRACK_UPDATED",
        payload={
            "source_id": "replay-radar",
            "source_track_id": "trk-1",
            "t": now,
            "pos": [12.0, 3.0],
            "vel": [0.5, 0.0],
            "quality": 0.8,
            "trust": 0.8,
        },
        ts=now,
    )
    store.close()
    monkeypatch.setenv("RADAR_REPLAY_DB", str(db_path))
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
    )
    saw_target = False
    for _ in range(10):
        output = pipeline.render_observations([])
        assert output.plan is not None
        if output.plan.stats.targets_count == 1:
            saw_target = True
            break
    assert saw_target is True
