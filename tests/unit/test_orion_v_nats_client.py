from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from qiki.services.operator_console.clients.nats_client import NATSClient


class _SubStub:
    def __init__(self) -> None:
        self.unsubscribed = False

    async def unsubscribe(self) -> None:
        self.unsubscribed = True


class _MetaStub:
    def __init__(self, timestamp) -> None:
        self.timestamp = timestamp


class _MsgStub:
    def __init__(self, *, data: bytes, subject: str, timestamp) -> None:
        self.data = data
        self.subject = subject
        self.metadata = _MetaStub(timestamp)
        self.acked = False

    async def ack(self) -> None:
        self.acked = True


class _PullSubStub:
    def __init__(self, messages: list[_MsgStub]) -> None:
        self._messages = messages
        self.unsubscribed = False

    async def fetch(self, *, batch: int, timeout: float) -> list[_MsgStub]:
        del batch, timeout
        return self._messages

    async def unsubscribe(self) -> None:
        self.unsubscribed = True


class _JsStub:
    def __init__(self, messages: list[_MsgStub]) -> None:
        self._messages = messages
        self.last_sub: _PullSubStub | None = None

    async def pull_subscribe(self, *_args, **_kwargs) -> _PullSubStub:
        self.last_sub = _PullSubStub(self._messages)
        return self.last_sub


def test_replace_subscription_unsubscribes_previous() -> None:
    client = NATSClient(url="nats://test:4222")
    created: list[_SubStub] = []

    async def factory() -> _SubStub:
        sub = _SubStub()
        created.append(sub)
        return sub

    async def run() -> None:
        await client._register_subscription("EVENTS", factory)
        first = client.subscriptions["EVENTS"]
        await client._register_subscription("EVENTS", factory)
        assert first.unsubscribed is True
        assert client.subscriptions["EVENTS"] is created[-1]
        assert len(client.subscriptions) == 1

    asyncio.run(run())


def test_resubscribe_all_replaces_existing_once() -> None:
    client = NATSClient(url="nats://test:4222")
    created = 0

    async def factory() -> _SubStub:
        nonlocal created
        created += 1
        return _SubStub()

    async def run() -> None:
        await client._register_subscription("EVENTS", factory)
        await client._resubscribe_all()
        assert created == 2
        assert len(client.subscriptions) == 1

    asyncio.run(run())


def test_fetch_events_history_uses_jetstream_timestamp() -> None:
    client = NATSClient(url="nats://test:4222")
    ts = datetime(2026, 2, 26, 6, 30, tzinfo=timezone.utc)
    msg = _MsgStub(data=b'{"kind":"incident"}', subject="qiki.events.v1.audit", timestamp=ts)
    js = _JsStub([msg])
    client.js = js  # type: ignore[assignment]

    history = asyncio.run(client.fetch_events_history(limit=1))

    assert len(history) == 1
    assert history[0]["timestamp"] == ts.timestamp()
    assert msg.acked is True
    assert js.last_sub is not None and js.last_sub.unsubscribed is True


def test_fetch_events_history_without_metadata_timestamp_is_none() -> None:
    client = NATSClient(url="nats://test:4222")
    msg = _MsgStub(data=b'{"kind":"incident"}', subject="qiki.events.v1.audit", timestamp=None)
    js = _JsStub([msg])
    client.js = js  # type: ignore[assignment]

    history = asyncio.run(client.fetch_events_history(limit=1))

    assert len(history) == 1
    assert history[0]["timestamp"] is None
