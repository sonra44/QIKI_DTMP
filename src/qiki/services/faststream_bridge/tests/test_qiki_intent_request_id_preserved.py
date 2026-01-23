from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from qiki.services.faststream_bridge.app import handle_qiki_intent
from qiki.services.faststream_bridge.mode_store import get_mode, reset_for_tests, set_mode
from qiki.shared.models.qiki_chat import QikiMode


class _DummyLogger:
    def info(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return


@pytest.mark.asyncio
async def test_qiki_intent_preserves_request_id_in_fallback() -> None:
    reset_for_tests()
    req_id = uuid4()
    payload = {
        "request_id": str(req_id),
        # Intentionally invalid for QikiChatRequestV1 (missing required fields)
        "text": "ping",
    }

    resp = await handle_qiki_intent(payload, _DummyLogger())  # type: ignore[arg-type]
    assert UUID(resp["request_id"]) == req_id
    assert resp["ok"] is False
    assert resp["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.asyncio
async def test_qiki_intent_generates_request_id_when_missing() -> None:
    reset_for_tests()
    payload = {"text": "ping"}
    resp = await handle_qiki_intent(payload, _DummyLogger())  # type: ignore[arg-type]
    assert UUID(resp["request_id"])
    assert resp["ok"] is False
    assert resp["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.asyncio
async def test_qiki_intent_response_mode_is_authoritative_state() -> None:
    reset_for_tests()
    set_mode(QikiMode.MISSION)
    payload = {
        "version": 1,
        "request_id": str(uuid4()),
        "ts_epoch_ms": 1,
        "mode_hint": "FACTORY",
        "input": {"text": "ping", "lang_hint": "auto"},
    }
    resp = await handle_qiki_intent(payload, _DummyLogger())  # type: ignore[arg-type]
    assert resp["ok"] is True
    assert resp["mode"] == "MISSION"


@pytest.mark.asyncio
async def test_qiki_intent_mode_change_updates_state() -> None:
    reset_for_tests()
    payload = {
        "version": 1,
        "request_id": str(uuid4()),
        "ts_epoch_ms": 1,
        "mode_hint": "FACTORY",
        "input": {"text": "mode mission", "lang_hint": "auto"},
    }
    resp = await handle_qiki_intent(payload, _DummyLogger())  # type: ignore[arg-type]
    assert resp["ok"] is True
    assert resp["mode"] == "MISSION"
    assert get_mode() == QikiMode.MISSION
