import pytest


@pytest.mark.asyncio
async def test_faststream_bridge_publishes_system_mode_on_startup(monkeypatch) -> None:
    pytest.importorskip("faststream")
    # Import lazily so we can monkeypatch module globals after import.
    from qiki.services.faststream_bridge import app as bridge_app
    from qiki.shared.nats_subjects import EVENTS_STREAM_NAME, SYSTEM_MODE_EVENT

    published: list[tuple[dict, str, str | None]] = []

    async def fake_publish(payload: dict, *, subject: str, stream: str | None = None) -> None:
        published.append((payload, subject, stream))

    async def fake_lag_start() -> None:
        return None

    monkeypatch.setattr(bridge_app.broker, "publish", fake_publish)
    monkeypatch.setattr(bridge_app._lag_monitor, "start", fake_lag_start)

    await bridge_app.after_startup()

    assert published, "expected at least one publish after startup"
    payload, subject, stream = published[-1]
    assert subject == SYSTEM_MODE_EVENT
    assert stream == EVENTS_STREAM_NAME
    assert payload.get("subject") == SYSTEM_MODE_EVENT
    assert payload.get("source") == "faststream_bridge"
    assert payload.get("event_schema_version") == 1
    assert payload.get("mode") in {"factory", "mission", "FACTORY", "MISSION"}
    assert isinstance(payload.get("timestamp"), str)
    assert isinstance(payload.get("ts_epoch"), (int, float))
