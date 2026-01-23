
from uuid import uuid4

from qiki.shared.models.qiki_chat import QikiChatResponseV1


def test_qiki_chat_response_accepts_requestId_alias() -> None:
    request_id = uuid4()
    payload = {
        "version": 1,
        "requestId": str(request_id),
        "ok": True,
        "mode": "FACTORY",
        "reply": {
            "title": {"en": "OK", "ru": "ОК"},
            "body": {"en": "hello", "ru": "привет"},
        },
        "proposals": [],
        "warnings": [],
        "error": None,
    }

    resp = QikiChatResponseV1.model_validate(payload)
    assert resp.request_id == request_id
