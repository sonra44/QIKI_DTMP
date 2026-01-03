from __future__ import annotations

import time
from uuid import uuid4

from qiki.services.qiki_chat.handler import handle_chat_request
from qiki.shared.models.qiki_chat import QikiChatInput, QikiChatRequestV1, QikiMode


def test_handle_chat_request_returns_ok_response() -> None:
    req = QikiChatRequestV1(
        request_id=uuid4(),
        ts_epoch_ms=int(time.time() * 1000),
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="hello", lang_hint="auto"),
    )
    resp = handle_chat_request(req)
    assert resp.ok is True
    assert resp.request_id == req.request_id
    assert resp.mode.value == "FACTORY"
    assert resp.reply is not None
    assert resp.reply.title.en
    assert resp.reply.title.ru
    assert resp.proposals
    assert resp.proposals[0].proposed_actions == []

