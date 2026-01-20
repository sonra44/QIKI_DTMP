from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from qiki.services.faststream_bridge.app import handle_qiki_intent


class _DummyLogger:
    def info(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return


@pytest.mark.asyncio
async def test_qiki_intent_preserves_request_id_in_fallback() -> None:
    req_id = uuid4()
    payload = {
        "request_id": str(req_id),
        # Intentionally invalid for QikiChatRequestV1 (missing required fields)
        "text": "ping",
    }

    resp = await handle_qiki_intent(payload, _DummyLogger())  # type: ignore[arg-type]
    assert UUID(resp["request_id"]) == req_id


@pytest.mark.asyncio
async def test_qiki_intent_generates_request_id_when_missing() -> None:
    payload = {"text": "ping"}
    resp = await handle_qiki_intent(payload, _DummyLogger())  # type: ignore[arg-type]
    assert UUID(resp["request_id"])

