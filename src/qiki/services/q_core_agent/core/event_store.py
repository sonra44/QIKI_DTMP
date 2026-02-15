"""EventStore with optional durable SQLite backend and async writes."""

from __future__ import annotations

import json
import os
import queue
import sqlite3
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Deque, Iterable, Optional
from uuid import uuid4


class TruthState(str, Enum):
    OK = "OK"
    NO_DATA = "NO_DATA"
    FALLBACK = "FALLBACK"
    INVALID = "INVALID"


@dataclass(frozen=True)
class SystemEvent:
    event_id: str
    ts: float
    subsystem: str
    event_type: str
    payload: dict[str, Any]
    tick_id: Optional[str]
    truth_state: TruthState
    reason: str

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["truth_state"] = self.truth_state.value
        return data


@dataclass(frozen=True)
class EventStoreStats:
    rows: int
    db_size_bytes: int
    oldest_ts: float | None
    newest_ts: float | None


class _BackendMode(str, Enum):
    MEMORY = "memory"
    SQLITE = "sqlite"
    HYBRID = "hybrid"


def _truth_state_from_any(value: TruthState | str) -> TruthState:
    if isinstance(value, TruthState):
        return value
    normalized = str(value or "").strip().upper()
    for state in TruthState:
        if state.value == normalized:
            return state
    return TruthState.INVALID


def _is_enabled(raw: str) -> bool:
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _parse_int(raw: str, default: int, *, min_value: int) -> int:
    try:
        value = int(raw)
    except Exception:
        return default
    return max(min_value, value)


def _parse_float(raw: str, default: float, *, min_value: float) -> float:
    try:
        value = float(raw)
    except Exception:
        return default
    return max(min_value, value)


class _SQLiteEventWriter:
    """Async batched writer for SQLite backend."""

    def __init__(
        self,
        db_path: str,
        *,
        queue_max: int,
        batch_size: int,
        flush_ms: int,
    ) -> None:
        self.db_path = str(db_path)
        self.queue_max = max(1, int(queue_max))
        self.batch_size = max(1, int(batch_size))
        self.flush_ms = max(1, int(flush_ms))
        self._queue: queue.Queue[tuple | object] = queue.Queue(maxsize=self.queue_max)
        self._sentinel = object()
        self._stop = threading.Event()
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._run, name="eventstore-sqlite-writer", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        try:
            self._queue.put_nowait(self._sentinel)
        except queue.Full:
            # force wait only during shutdown path
            self._queue.put(self._sentinel)
        self._thread.join()

    def append_row(self, row: tuple) -> bool:
        try:
            self._queue.put_nowait(row)
            return True
        except queue.Full:
            return False

    def flush(self) -> None:
        self._queue.join()

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    @property
    def last_error(self) -> Exception | None:
        return self._error

    def _run(self) -> None:
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        try:
            pending: list[tuple] = []
            while True:
                timeout = max(0.001, self.flush_ms / 1000.0)
                try:
                    item = self._queue.get(timeout=timeout)
                except queue.Empty:
                    item = None

                if item is self._sentinel:
                    if pending:
                        self._insert_many(conn, pending)
                        for _ in pending:
                            self._queue.task_done()
                        pending = []
                    self._queue.task_done()
                    break

                if item is not None:
                    pending.append(item)  # type: ignore[arg-type]

                if pending and (len(pending) >= self.batch_size or item is None):
                    self._insert_many(conn, pending)
                    for _ in pending:
                        self._queue.task_done()
                    pending = []
        except Exception as exc:  # noqa: BLE001
            self._error = exc
            # drain queue so producers are not blocked forever
            while True:
                try:
                    _ = self._queue.get_nowait()
                    self._queue.task_done()
                except queue.Empty:
                    break
        finally:
            conn.close()

    def _insert_many(self, conn: sqlite3.Connection, rows: Iterable[tuple]) -> None:
        conn.executemany(
            """
            INSERT INTO events (
                ts, subsystem, event_type, truth_state, session_id, payload_json, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


class EventStore:
    def __init__(
        self,
        maxlen: int = 1000,
        enabled: bool = True,
        *,
        backend: str = "memory",
        db_path: str | None = None,
        batch_size: int = 200,
        queue_max: int = 10_000,
        flush_ms: int = 50,
        retention_hours: float = 24.0,
        max_db_mb: float = 512.0,
        vacuum_on_start: bool = False,
        strict: bool = False,
    ):
        self.maxlen = max(1, int(maxlen))
        self.enabled = bool(enabled)
        self._events: Deque[SystemEvent] = deque(maxlen=self.maxlen)

        backend_raw = str(backend or "memory").strip().lower()
        if backend_raw not in {mode.value for mode in _BackendMode}:
            backend_raw = _BackendMode.MEMORY.value
        self.backend = _BackendMode(backend_raw)
        self.db_path = str(db_path or os.getenv("EVENTSTORE_DB_PATH", "artifacts/eventstore.sqlite"))
        self.batch_size = max(1, int(batch_size))
        self.queue_max = max(100, int(queue_max))
        self.flush_ms = max(1, int(flush_ms))
        self.retention_hours = max(0.0, float(retention_hours))
        self.max_db_mb = max(1.0, float(max_db_mb))
        self.strict = bool(strict)

        self._sqlite_writer: _SQLiteEventWriter | None = None
        self._sqlite_conn: sqlite3.Connection | None = None
        self._sqlite_dropped = 0
        self._last_drop_emit = 0.0
        self._last_lag_emit = 0.0
        self._last_retention_run = 0.0

        self._db_schema_version = 1
        self._retention_batch_rows = 5000
        self._retention_check_period_s = 30.0

        if self.enabled and self.backend in {_BackendMode.SQLITE, _BackendMode.HYBRID}:
            self._open_sqlite(vacuum_on_start=vacuum_on_start)
            self._emit_lifecycle_event(
                event_type="EVENTSTORE_DB_OPENED",
                reason="DB_OPENED",
                payload={"path": self.db_path, "schema_version": self._db_schema_version},
                truth_state=TruthState.OK,
            )

    @classmethod
    def from_env(cls) -> "EventStore":
        maxlen_raw = os.getenv("QIKI_EVENT_STORE_MAXLEN", "1000")
        enable_raw = os.getenv("QIKI_EVENT_STORE_ENABLE", "true")
        backend = os.getenv("EVENTSTORE_BACKEND", "memory")
        db_path = os.getenv("EVENTSTORE_DB_PATH", "artifacts/eventstore.sqlite")
        batch_size = _parse_int(os.getenv("EVENTSTORE_BATCH_SIZE", "200"), 200, min_value=1)
        queue_max = _parse_int(os.getenv("EVENTSTORE_QUEUE_MAX", "10000"), 10_000, min_value=100)
        flush_ms = _parse_int(os.getenv("EVENTSTORE_FLUSH_MS", "50"), 50, min_value=1)
        retention_hours = _parse_float(os.getenv("EVENTSTORE_RETENTION_HOURS", "24"), 24.0, min_value=0.0)
        max_db_mb = _parse_float(os.getenv("EVENTSTORE_MAX_DB_MB", "512"), 512.0, min_value=1.0)
        vacuum_on_start = _is_enabled(os.getenv("EVENTSTORE_VACUUM_ON_START", "0"))
        strict = _is_enabled(os.getenv("EVENTSTORE_STRICT", "0"))
        try:
            maxlen = int(maxlen_raw)
        except Exception:
            maxlen = 1000
        return cls(
            maxlen=maxlen,
            enabled=_is_enabled(enable_raw),
            backend=backend,
            db_path=db_path,
            batch_size=batch_size,
            queue_max=queue_max,
            flush_ms=flush_ms,
            retention_hours=retention_hours,
            max_db_mb=max_db_mb,
            vacuum_on_start=vacuum_on_start,
            strict=strict,
        )

    def append(self, event: SystemEvent) -> Optional[SystemEvent]:
        if not self.enabled:
            return None
        self._events.append(event)
        self._append_sqlite(event)
        self._maybe_run_retention(event.ts)
        return event

    def append_new(
        self,
        *,
        subsystem: str,
        event_type: str,
        payload: dict[str, Any],
        truth_state: TruthState | str = TruthState.OK,
        reason: str = "",
        tick_id: Optional[str] = None,
        ts: float | None = None,
    ) -> Optional[SystemEvent]:
        event = SystemEvent(
            event_id=str(uuid4()),
            ts=float(time.time() if ts is None else ts),
            subsystem=str(subsystem),
            event_type=str(event_type),
            payload=dict(payload),
            tick_id=tick_id,
            truth_state=_truth_state_from_any(truth_state),
            reason=str(reason or ""),
        )
        return self.append(event)

    def recent(self, n: int = 20) -> list[SystemEvent]:
        limit = max(0, int(n))
        if limit == 0:
            return []
        return list(self._events)[-limit:]

    def snapshot(self) -> list[SystemEvent]:
        """Return a stable in-memory copy for non-blocking readers."""
        return list(self._events)

    def query(
        self,
        *,
        from_ts: float | None = None,
        to_ts: float | None = None,
        types: set[str] | frozenset[str] | None = None,
        subsystems: set[str] | frozenset[str] | None = None,
        truth_states: set[str] | frozenset[str] | None = None,
        limit: int | None = None,
        order: str = "asc",
    ) -> list[SystemEvent]:
        active_types = set(types or ())
        active_subsystems = set(subsystems or ())
        active_truth = {str(item).upper() for item in (truth_states or ())}
        max_rows = None if limit is None else max(1, int(limit))
        normalized_order = "DESC" if str(order).strip().lower() == "desc" else "ASC"

        if self.backend in {_BackendMode.SQLITE, _BackendMode.HYBRID} and self._sqlite_conn is not None:
            return self._query_sqlite(
                from_ts=from_ts,
                to_ts=to_ts,
                types=active_types,
                subsystems=active_subsystems,
                truth_states=active_truth,
                limit=max_rows,
                order=normalized_order,
            )

        events = self.iter_events(from_ts=from_ts, to_ts=to_ts)
        result: list[SystemEvent] = []
        iterable = reversed(events) if normalized_order == "DESC" else events
        for event in iterable:
            if active_types and event.event_type not in active_types:
                continue
            if active_subsystems and event.subsystem not in active_subsystems:
                continue
            if active_truth and event.truth_state.value.upper() not in active_truth:
                continue
            result.append(event)
            if max_rows is not None and len(result) >= max_rows:
                break
        if normalized_order == "DESC":
            result = list(result)
        return result

    def iter_events(
        self,
        *,
        from_ts: Optional[float] = None,
        to_ts: Optional[float] = None,
    ) -> list[SystemEvent]:
        result: list[SystemEvent] = []
        for event in self._events:
            if from_ts is not None and event.ts < float(from_ts):
                continue
            if to_ts is not None and event.ts > float(to_ts):
                continue
            result.append(event)
        return result

    def filter(
        self,
        *,
        subsystem: Optional[str] = None,
        event_type: Optional[str] = None,
        truth_state: Optional[TruthState | str] = None,
    ) -> list[SystemEvent]:
        expected_truth: Optional[TruthState] = None
        if truth_state is not None:
            expected_truth = _truth_state_from_any(truth_state)
        result: list[SystemEvent] = []
        for event in self._events:
            if subsystem is not None and event.subsystem != subsystem:
                continue
            if event_type is not None and event.event_type != event_type:
                continue
            if expected_truth is not None and event.truth_state != expected_truth:
                continue
            result.append(event)
        return result

    def stats(self) -> EventStoreStats:
        if self.backend in {_BackendMode.SQLITE, _BackendMode.HYBRID} and self._sqlite_conn is not None:
            self._flush_sqlite_writer()
            row = self._sqlite_conn.execute(
                "SELECT COUNT(*), MIN(ts), MAX(ts) FROM events"
            ).fetchone()
            db_size = self._db_size_bytes()
            rows = int(row[0] if row and row[0] is not None else 0)
            oldest = float(row[1]) if row and row[1] is not None else None
            newest = float(row[2]) if row and row[2] is not None else None
            return EventStoreStats(rows=rows, db_size_bytes=db_size, oldest_ts=oldest, newest_ts=newest)
        events = list(self._events)
        if not events:
            return EventStoreStats(rows=0, db_size_bytes=0, oldest_ts=None, newest_ts=None)
        return EventStoreStats(
            rows=len(events),
            db_size_bytes=0,
            oldest_ts=min(event.ts for event in events),
            newest_ts=max(event.ts for event in events),
        )

    def close(self) -> None:
        if self._sqlite_writer is not None:
            writer = self._sqlite_writer
            self._flush_sqlite_writer()
            writer.close()
            self._sqlite_writer = None
            if writer.last_error is not None and self.strict:
                raise RuntimeError(f"eventstore sqlite writer failed during close: {writer.last_error}")
        if self._sqlite_conn is not None:
            self._sqlite_conn.close()
            self._sqlite_conn = None

    def export_jsonl(self, path: str) -> int:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with out_path.open("w", encoding="utf-8") as handle:
            for event in self._events:
                handle.write(json.dumps(event.to_json_dict(), ensure_ascii=True))
                handle.write("\n")
                count += 1
        return count

    # SQLite internals

    def _open_sqlite(self, *, vacuum_on_start: bool) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._sqlite_conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        self._sqlite_conn.execute("PRAGMA journal_mode=WAL")
        self._sqlite_conn.execute("PRAGMA synchronous=NORMAL")
        self._sqlite_conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                ts REAL NOT NULL,
                subsystem TEXT NOT NULL,
                event_type TEXT NOT NULL,
                truth_state TEXT,
                session_id TEXT,
                payload_json TEXT NOT NULL,
                schema_version INTEGER NOT NULL
            )
            """
        )
        self._sqlite_conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")
        self._sqlite_conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events(event_type, ts)")
        self._sqlite_conn.execute("CREATE INDEX IF NOT EXISTS idx_events_subsystem_ts ON events(subsystem, ts)")
        self._sqlite_conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session_ts ON events(session_id, ts)")
        self._sqlite_conn.commit()
        if vacuum_on_start:
            self._sqlite_conn.execute("VACUUM")
            self._sqlite_conn.commit()

        self._sqlite_writer = _SQLiteEventWriter(
            self.db_path,
            queue_max=self.queue_max,
            batch_size=self.batch_size,
            flush_ms=self.flush_ms,
        )
        self._sqlite_writer.start()

    def _append_sqlite(self, event: SystemEvent) -> None:
        if self._sqlite_writer is None:
            return
        if self._sqlite_writer.last_error is not None:
            if self.strict:
                raise RuntimeError(f"eventstore sqlite writer failed: {self._sqlite_writer.last_error}")
            return

        session_id = ""
        if isinstance(event.payload, dict):
            maybe = event.payload.get("session_id")
            if maybe is not None:
                session_id = str(maybe)
        row = (
            float(event.ts),
            str(event.subsystem),
            str(event.event_type),
            event.truth_state.value,
            session_id,
            json.dumps(event.payload, ensure_ascii=True),
            int(self._db_schema_version),
        )
        enqueued = self._sqlite_writer.append_row(row)
        if enqueued:
            self._maybe_emit_write_lag()
            return

        self._sqlite_dropped += 1
        if self.strict:
            raise RuntimeError("eventstore queue overflow")
        now = time.time()
        if now - self._last_drop_emit >= 1.0:
            dropped = self._sqlite_dropped
            self._sqlite_dropped = 0
            self._last_drop_emit = now
            self._emit_lifecycle_event(
                event_type="EVENTSTORE_DROP",
                reason="QUEUE_OVERFLOW",
                payload={"count": dropped, "reason": "QUEUE_OVERFLOW"},
                truth_state=TruthState.NO_DATA,
            )

    def _maybe_emit_write_lag(self) -> None:
        if self._sqlite_writer is None:
            return
        depth = self._sqlite_writer.queue_depth
        if depth < int(self.queue_max * 0.8):
            return
        now = time.time()
        if now - self._last_lag_emit < 1.0:
            return
        self._last_lag_emit = now
        self._emit_lifecycle_event(
            event_type="EVENTSTORE_DB_WRITE_LAG",
            reason="QUEUE_LAG",
            payload={"queue_depth": depth, "dropped": self._sqlite_dropped},
            truth_state=TruthState.NO_DATA,
        )

    def _emit_lifecycle_event(
        self,
        *,
        event_type: str,
        reason: str,
        payload: dict[str, Any],
        truth_state: TruthState,
    ) -> None:
        event = SystemEvent(
            event_id=str(uuid4()),
            ts=time.time(),
            subsystem="EVENTSTORE",
            event_type=event_type,
            payload=dict(payload),
            tick_id=None,
            truth_state=truth_state,
            reason=reason,
        )
        self._events.append(event)
        # Best effort for durable audit trail.
        if self._sqlite_writer is not None:
            session_id = ""
            row = (
                float(event.ts),
                event.subsystem,
                event.event_type,
                event.truth_state.value,
                session_id,
                json.dumps(event.payload, ensure_ascii=True),
                int(self._db_schema_version),
            )
            _ = self._sqlite_writer.append_row(row)

    def _flush_sqlite_writer(self) -> None:
        if self._sqlite_writer is not None:
            self._sqlite_writer.flush()

    def _query_sqlite(
        self,
        *,
        from_ts: float | None,
        to_ts: float | None,
        types: set[str],
        subsystems: set[str],
        truth_states: set[str],
        limit: int | None,
        order: str,
    ) -> list[SystemEvent]:
        assert self._sqlite_conn is not None
        self._flush_sqlite_writer()

        clauses: list[str] = []
        params: list[Any] = []
        if from_ts is not None:
            clauses.append("ts >= ?")
            params.append(float(from_ts))
        if to_ts is not None:
            clauses.append("ts <= ?")
            params.append(float(to_ts))
        if types:
            placeholders = ",".join("?" for _ in types)
            clauses.append(f"event_type IN ({placeholders})")
            params.extend(sorted(types))
        if subsystems:
            placeholders = ",".join("?" for _ in subsystems)
            clauses.append(f"subsystem IN ({placeholders})")
            params.extend(sorted(subsystems))
        if truth_states:
            placeholders = ",".join("?" for _ in truth_states)
            clauses.append(f"truth_state IN ({placeholders})")
            params.extend(sorted(truth_states))

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_sql = ""
        if limit is not None:
            limit_sql = " LIMIT ?"
            params.append(int(limit))

        rows = self._sqlite_conn.execute(
            f"""
            SELECT ts, subsystem, event_type, truth_state, payload_json
            FROM events
            {where_sql}
            ORDER BY ts {order}, id {order}
            {limit_sql}
            """,
            params,
        ).fetchall()
        result: list[SystemEvent] = []
        for idx, row in enumerate(rows):
            ts, subsystem, event_type, truth_state, payload_json = row
            payload: dict[str, Any]
            try:
                loaded = json.loads(str(payload_json))
                payload = loaded if isinstance(loaded, dict) else {}
            except Exception:
                payload = {}
            result.append(
                SystemEvent(
                    event_id=f"sqlite:{idx}:{float(ts):.6f}",
                    ts=float(ts),
                    subsystem=str(subsystem),
                    event_type=str(event_type),
                    payload=payload,
                    tick_id=None,
                    truth_state=_truth_state_from_any(str(truth_state or "")),
                    reason=str(payload.get("reason", event_type)) if isinstance(payload, dict) else str(event_type),
                )
            )
        return result

    def _db_size_bytes(self) -> int:
        db_file = Path(self.db_path)
        wal_file = Path(f"{self.db_path}-wal")
        shm_file = Path(f"{self.db_path}-shm")
        total = 0
        for path in (db_file, wal_file, shm_file):
            if path.exists():
                total += path.stat().st_size
        return total

    def _maybe_run_retention(self, now_ts: float) -> None:
        if self._sqlite_conn is None:
            return
        now = float(now_ts)
        if now - self._last_retention_run < self._retention_check_period_s:
            return
        self._last_retention_run = now
        start = time.time()
        deleted_rows = 0
        self._flush_sqlite_writer()

        if self.retention_hours > 0.0:
            cutoff = now - (self.retention_hours * 3600.0)
            while True:
                cur = self._sqlite_conn.execute(
                    "DELETE FROM events WHERE id IN (SELECT id FROM events WHERE ts < ? ORDER BY ts ASC LIMIT ?)",
                    (float(cutoff), int(self._retention_batch_rows)),
                )
                removed = int(cur.rowcount or 0)
                self._sqlite_conn.commit()
                deleted_rows += removed
                if removed < self._retention_batch_rows:
                    break

        max_bytes = int(self.max_db_mb * 1024.0 * 1024.0)
        while self._db_size_bytes() > max_bytes:
            cur = self._sqlite_conn.execute(
                "DELETE FROM events WHERE id IN (SELECT id FROM events ORDER BY ts ASC LIMIT ?)",
                (int(self._retention_batch_rows),),
            )
            removed = int(cur.rowcount or 0)
            self._sqlite_conn.commit()
            deleted_rows += removed
            if removed <= 0:
                break

        duration_ms = (time.time() - start) * 1000.0
        self._emit_lifecycle_event(
            event_type="EVENTSTORE_RETENTION_RUN",
            reason="RETENTION",
            payload={"deleted_rows": deleted_rows, "duration_ms": duration_ms},
            truth_state=TruthState.OK,
        )
