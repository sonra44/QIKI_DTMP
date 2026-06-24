from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
from typing import Any

import pytest

from qiki.services.q_core_agent.core.event_store import EventStore


class _TrackingLock:
    def __init__(self) -> None:
        self.depth = 0

    def __enter__(self) -> "_TrackingLock":
        self.depth += 1
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.depth -= 1

    @property
    def held(self) -> bool:
        return self.depth > 0


class _LockAssertingConnection:
    def __init__(self, conn: Any, lock: _TrackingLock) -> None:
        self._conn = conn
        self._lock = lock

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        assert self._lock.held, "sqlite connection used without _sqlite_lock"
        return self._conn.execute(*args, **kwargs)

    def commit(self) -> Any:
        assert self._lock.held, "sqlite commit used without _sqlite_lock"
        return self._conn.commit()

    def close(self) -> Any:
        return self._conn.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


class _RetentionEventsLockAssertingConnection(_LockAssertingConnection):
    def __init__(self, conn: Any, sqlite_lock: _TrackingLock, events_lock: _TrackingLock) -> None:
        super().__init__(conn, sqlite_lock)
        self._events_lock = events_lock

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        sql = str(args[0]).lstrip().upper() if args else ""
        if sql.startswith("DELETE"):
            assert not self._events_lock.held, "retention DELETE ran under _events_lock"
        return super().execute(*args, **kwargs)


@pytest.mark.parametrize("backend", ["memory", "hybrid"])
def test_event_store_memory_backed_modes_have_reentrant_events_lock(
    backend: str,
    tmp_path: Path,
) -> None:
    store = EventStore(
        backend=backend,
        db_path=str(tmp_path / "events.sqlite"),
        maxlen=10,
    )

    try:
        assert isinstance(store._events_lock, type(threading.RLock()))
    finally:
        store.close()


@pytest.mark.parametrize("backend", ["memory", "hybrid"])
def test_event_store_memory_backed_modes_handle_concurrent_read_write_access(
    backend: str,
    tmp_path: Path,
) -> None:
    writers = 4
    per_writer = 100
    store = EventStore(
        backend=backend,
        db_path=str(tmp_path / "events.sqlite"),
        maxlen=(writers * per_writer) + 10,
    )
    errors: list[BaseException] = []

    def write_batch(writer_id: int) -> None:
        for index in range(per_writer):
            store.append_new(
                subsystem=f"writer-{writer_id}",
                event_type="thread_safety_probe",
                payload={"writer": writer_id, "index": index},
                reason="",
                ts=(writer_id * per_writer) + index,
            )

    def read_loop() -> None:
        try:
            for _ in range(200):
                store.snapshot()
                store.recent(20)
                if backend == "memory":
                    store.query(types={"thread_safety_probe"}, order="desc", limit=10)
                store.iter_events(from_ts=0)
                store.filter(event_type="thread_safety_probe")
        except BaseException as exc:  # pragma: no cover - surfaced after threads join.
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=writers + 3) as executor:
        futures = [executor.submit(write_batch, writer_id) for writer_id in range(writers)]
        futures.extend(executor.submit(read_loop) for _ in range(3))
        for future in futures:
            future.result(timeout=5)

    try:
        assert errors == []
        events = [event for event in store.snapshot() if event.event_type == "thread_safety_probe"]
        assert len(events) == writers * per_writer
        assert len({event.event_id for event in events}) == writers * per_writer
    finally:
        store.close()


def test_event_store_sqlite_stats_and_query_use_sqlite_lock(tmp_path: Path) -> None:
    store = EventStore(
        backend="sqlite",
        db_path=str(tmp_path / "events.sqlite"),
        flush_ms=5,
        batch_size=10,
        queue_max=1000,
    )
    try:
        store.append_new(subsystem="LOCK", event_type="QUERY", payload={}, ts=1.0)
        store._flush_sqlite_writer()
        lock = _TrackingLock()
        store._sqlite_lock = lock  # type: ignore[attr-defined]
        store._sqlite_conn = _LockAssertingConnection(store._sqlite_conn, lock)  # type: ignore[arg-type]

        assert store.stats().rows >= 1
        assert store.query(types={"QUERY"})
    finally:
        store.close()


def test_event_store_sqlite_retention_uses_sqlite_lock(tmp_path: Path) -> None:
    store = EventStore(
        backend="sqlite",
        db_path=str(tmp_path / "events.sqlite"),
        flush_ms=5,
        batch_size=10,
        queue_max=1000,
        retention_hours=1.0 / 3600.0,
    )
    try:
        store.append_new(subsystem="LOCK", event_type="OLD", payload={}, ts=1.0)
        store._flush_sqlite_writer()
        store._last_retention_run = 0.0
        store._retention_check_period_s = 0.0
        lock = _TrackingLock()
        store._sqlite_lock = lock  # type: ignore[attr-defined]
        store._sqlite_conn = _LockAssertingConnection(store._sqlite_conn, lock)  # type: ignore[arg-type]

        store.append_new(subsystem="LOCK", event_type="NEW", payload={}, ts=7200.0)
    finally:
        store.close()


def test_event_store_sqlite_retention_runs_outside_events_lock(tmp_path: Path) -> None:
    store = EventStore(
        backend="sqlite",
        db_path=str(tmp_path / "events.sqlite"),
        flush_ms=5,
        batch_size=10,
        queue_max=1000,
        retention_hours=1.0 / 3600.0,
    )
    try:
        store.append_new(subsystem="LOCK", event_type="OLD", payload={}, ts=1.0)
        store._flush_sqlite_writer()
        store._last_retention_run = 0.0
        store._retention_check_period_s = 0.0
        sqlite_lock = _TrackingLock()
        events_lock = _TrackingLock()
        store._sqlite_lock = sqlite_lock  # type: ignore[attr-defined]
        store._events_lock = events_lock  # type: ignore[assignment]
        store._sqlite_conn = _RetentionEventsLockAssertingConnection(  # type: ignore[arg-type]
            store._sqlite_conn,
            sqlite_lock,
            events_lock,
        )

        store.append_new(subsystem="LOCK", event_type="NEW", payload={}, ts=7200.0)
    finally:
        store.close()
