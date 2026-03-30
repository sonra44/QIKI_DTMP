from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from qiki.services.faststream_bridge.app import _publish_system_mode
from qiki.shared.models.qiki_chat import QikiMode
from qiki.shared.nats_subjects import SYSTEM_MODE_EVENT


@pytest.mark.asyncio
async def test_publish_system_mode_uses_jetstream_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    publish = AsyncMock()
    js = SimpleNamespace(publish=publish)

    nc = SimpleNamespace(
        jetstream=lambda: js,
        close=AsyncMock(),
    )

    async def connect(*_args, **_kwargs):
        return nc

    fake_nats = SimpleNamespace(connect=connect)
    monkeypatch.setattr("qiki.services.faststream_bridge.app.nats", fake_nats, raising=False)

    logger = Mock()
    await _publish_system_mode(QikiMode.FACTORY, logger_=logger)

    assert publish.await_count == 1
    (subject, payload_bytes), _kwargs = publish.await_args
    assert subject == SYSTEM_MODE_EVENT
    payload = json.loads(payload_bytes.decode("utf-8"))
    assert payload["mode"] == "FACTORY"
