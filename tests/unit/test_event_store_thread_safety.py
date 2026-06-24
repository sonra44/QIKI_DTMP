from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

import pytest

from qiki.services.q_core_agent.core.event_store import EventStore


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
