from __future__ import annotations

from project_introspector.emitter import EventEmitter
from project_introspector.models import RuntimeEvent


class _FailingClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, endpoint: str, json):
        raise RuntimeError("boom")


def test_emitter_tracks_dropped_events_when_buffer_overflows() -> None:
    emitter = EventEmitter(
        endpoint="http://unused/events/runtime",
        project_name="demo",
        batch_size=999,
        max_buffer_size=2,
        register_atexit=False,
    )
    for index in range(3):
        emitter.emit(
            RuntimeEvent(
                event_type="call",
                project_name="demo",
                module_path="pkg.module",
                qualified_name=f"pkg.module.fn{index}",
            )
        )

    health = emitter.health()
    assert emitter.buffer_size == 2
    assert emitter.dropped_events_count == 1
    assert health["dropped_events_count"] == 1


def test_emitter_tracks_flush_failures_and_keeps_buffer(monkeypatch) -> None:
    emitter = EventEmitter(
        endpoint="http://unused/events/runtime",
        project_name="demo",
        batch_size=999,
        max_buffer_size=10,
        register_atexit=False,
    )
    emitter.emit(
        RuntimeEvent(
            event_type="call",
            project_name="demo",
            module_path="pkg.module",
            qualified_name="pkg.module.fn",
        )
    )
    monkeypatch.setattr(emitter, "_build_client", lambda: _FailingClient())

    flushed = emitter.flush(suppress_errors=True)

    assert flushed == 0
    assert emitter.flush_failures_count == 1
    assert emitter.buffer_size == 1
