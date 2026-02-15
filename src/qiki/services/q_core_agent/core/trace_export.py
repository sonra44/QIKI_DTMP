"""Asynchronous EventStore JSONL export with stable envelope contract."""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .event_store import EventStore, SystemEvent, TruthState

_EXPORT_SCHEMA_VERSION = 1
_DEFAULT_WINDOW_SECONDS = 60.0
_DEFAULT_MAX_LINES = 10_000
_WRITE_BATCH_SIZE = 1_000
_SENTINEL = object()


@dataclass(frozen=True)
class TraceExportFilter:
    from_ts: float | None = None
    to_ts: float | None = None
    types: frozenset[str] = frozenset()
    subsystems: frozenset[str] = frozenset()
    truth_states: frozenset[str] = frozenset()
    max_lines: int = _DEFAULT_MAX_LINES
    sample_every_by_type: dict[str, int] | None = None


@dataclass(frozen=True)
class TraceExportResult:
    out_path: str
    lines_written: int
    duration_ms: float
    from_ts: float
    to_ts: float


class _AsyncJsonlWriter:
    def __init__(self, out_path: str):
        self._out_path = str(out_path)
        self._queue: queue.Queue[object] = queue.Queue(maxsize=8)
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._run, name="trace-jsonl-writer", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def submit_batch(self, lines: list[str]) -> None:
        if lines:
            self._queue.put(lines)

    def finish(self) -> None:
        self._queue.put(_SENTINEL)
        self._thread.join()
        if self._error is not None:
            raise self._error

    def _run(self) -> None:
        try:
            out_path = Path(self._out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("w", encoding="utf-8") as handle:
                while True:
                    item = self._queue.get()
                    if item is _SENTINEL:
                        break
                    for line in item:
                        handle.write(line)
        except Exception as exc:  # noqa: BLE001
            self._error = exc


def parse_csv_set(raw: str | None) -> frozenset[str]:
    if raw is None:
        return frozenset()
    values = [item.strip() for item in str(raw).split(",")]
    return frozenset(item for item in values if item)


def parse_sample_map(raw: str | None) -> dict[str, int]:
    if not raw:
        return {}
    result: dict[str, int] = {}
    for chunk in str(raw).split(","):
        item = chunk.strip()
        if not item:
            continue
        if "=" not in item:
            continue
        event_type, step_raw = item.split("=", 1)
        key = event_type.strip()
        try:
            step = max(1, int(step_raw.strip()))
        except Exception:
            continue
        if key:
            result[key] = step
    return result


def build_export_envelope(event: SystemEvent) -> dict:
    session_value = ""
    if isinstance(event.payload, dict):
        maybe = event.payload.get("session_id", "")
        if maybe is not None:
            session_value = str(maybe)
    return {
        "schema_version": _EXPORT_SCHEMA_VERSION,
        "ts": float(event.ts),
        "subsystem": str(event.subsystem),
        "event_type": str(event.event_type),
        "truth_state": event.truth_state.value if isinstance(event.truth_state, TruthState) else str(event.truth_state),
        "reason": str(event.reason or ""),
        "payload": event.payload,
        "session_id": session_value,
    }


def _matches_filter(event: SystemEvent, export_filter: TraceExportFilter) -> bool:
    if export_filter.from_ts is not None and event.ts < export_filter.from_ts:
        return False
    if export_filter.to_ts is not None and event.ts > export_filter.to_ts:
        return False
    if export_filter.types and event.event_type not in export_filter.types:
        return False
    if export_filter.subsystems and event.subsystem not in export_filter.subsystems:
        return False
    if export_filter.truth_states:
        if event.truth_state.value not in export_filter.truth_states and str(event.truth_state) not in export_filter.truth_states:
            return False
    return True


def _filtered_events_snapshot(events: Iterable[SystemEvent], export_filter: TraceExportFilter) -> list[SystemEvent]:
    sample_cfg = export_filter.sample_every_by_type or {}
    sampled_seen: dict[str, int] = {}
    output: list[SystemEvent] = []
    for event in events:
        if not _matches_filter(event, export_filter):
            continue
        step = sample_cfg.get(event.event_type)
        if step is not None:
            count = sampled_seen.get(event.event_type, 0) + 1
            sampled_seen[event.event_type] = count
            if (count - 1) % step != 0:
                continue
        output.append(event)
        if len(output) >= max(1, int(export_filter.max_lines)):
            break
    return output


def export_event_store_jsonl_async(
    event_store: EventStore,
    out_path: str,
    *,
    export_filter: TraceExportFilter | None = None,
    now_ts: float | None = None,
) -> TraceExportResult:
    now = float(time.time() if now_ts is None else now_ts)
    active_filter = export_filter or TraceExportFilter(
        from_ts=now - _DEFAULT_WINDOW_SECONDS,
        to_ts=now,
        max_lines=_DEFAULT_MAX_LINES,
    )
    from_ts = active_filter.from_ts if active_filter.from_ts is not None else (now - _DEFAULT_WINDOW_SECONDS)
    to_ts = active_filter.to_ts if active_filter.to_ts is not None else now
    normalized_filter = TraceExportFilter(
        from_ts=float(from_ts),
        to_ts=float(to_ts),
        types=frozenset(active_filter.types),
        subsystems=frozenset(active_filter.subsystems),
        truth_states=frozenset(active_filter.truth_states),
        max_lines=max(1, int(active_filter.max_lines)),
        sample_every_by_type=dict(active_filter.sample_every_by_type or {}),
    )
    start_ts = time.time()
    event_store.append_new(
        subsystem="TRACE",
        event_type="TRACE_EXPORT_STARTED",
        payload={
            "out_path": str(out_path),
            "from_ts": float(normalized_filter.from_ts),
            "to_ts": float(normalized_filter.to_ts),
            "filters": {
                "types": sorted(normalized_filter.types),
                "subsystems": sorted(normalized_filter.subsystems),
                "truth": sorted(normalized_filter.truth_states),
                "sample": normalized_filter.sample_every_by_type,
                "max_lines": int(normalized_filter.max_lines),
            },
            "lines_written": 0,
            "duration_ms": 0.0,
            "error": "",
        },
        truth_state=TruthState.OK,
        reason="TRACE_EXPORT_STARTED",
    )
    snapshot = event_store.query(
        from_ts=normalized_filter.from_ts,
        to_ts=normalized_filter.to_ts,
        types=set(normalized_filter.types),
        subsystems=set(normalized_filter.subsystems),
        truth_states=set(normalized_filter.truth_states),
        limit=normalized_filter.max_lines,
        order="asc",
    )
    writer = _AsyncJsonlWriter(str(out_path))
    lines_written = 0
    try:
        writer.start()
        batch: list[str] = []
        for event in _filtered_events_snapshot(snapshot, normalized_filter):
            envelope = build_export_envelope(event)
            batch.append(f"{json.dumps(envelope, ensure_ascii=True)}\n")
            lines_written += 1
            if len(batch) >= _WRITE_BATCH_SIZE:
                writer.submit_batch(batch)
                batch = []
        if batch:
            writer.submit_batch(batch)
        writer.finish()
        duration_ms = (time.time() - start_ts) * 1000.0
        event_store.append_new(
            subsystem="TRACE",
            event_type="TRACE_EXPORT_FINISHED",
            payload={
                "out_path": str(out_path),
                "from_ts": float(normalized_filter.from_ts),
                "to_ts": float(normalized_filter.to_ts),
                "filters": {
                    "types": sorted(normalized_filter.types),
                    "subsystems": sorted(normalized_filter.subsystems),
                    "truth": sorted(normalized_filter.truth_states),
                    "sample": normalized_filter.sample_every_by_type,
                    "max_lines": int(normalized_filter.max_lines),
                },
                "lines_written": int(lines_written),
                "duration_ms": float(duration_ms),
                "error": "",
            },
            truth_state=TruthState.OK,
            reason="TRACE_EXPORT_FINISHED",
        )
        return TraceExportResult(
            out_path=str(out_path),
            lines_written=int(lines_written),
            duration_ms=float(duration_ms),
            from_ts=float(normalized_filter.from_ts),
            to_ts=float(normalized_filter.to_ts),
        )
    except Exception as exc:  # noqa: BLE001
        duration_ms = (time.time() - start_ts) * 1000.0
        event_store.append_new(
            subsystem="TRACE",
            event_type="TRACE_EXPORT_FAILED",
            payload={
                "out_path": str(out_path),
                "from_ts": float(normalized_filter.from_ts),
                "to_ts": float(normalized_filter.to_ts),
                "filters": {
                    "types": sorted(normalized_filter.types),
                    "subsystems": sorted(normalized_filter.subsystems),
                    "truth": sorted(normalized_filter.truth_states),
                    "sample": normalized_filter.sample_every_by_type,
                    "max_lines": int(normalized_filter.max_lines),
                },
                "lines_written": int(lines_written),
                "duration_ms": float(duration_ms),
                "error": str(exc),
            },
            truth_state=TruthState.NO_DATA,
            reason="TRACE_EXPORT_FAILED",
        )
        raise
