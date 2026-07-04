"""M0a: secrets are never accepted from the bus.

Gate (F5_QIKI_DIALOG_SYSTEM_DESIGN.md §6, M0a): set_key over the bus does NOT
mutate the responder's environment; the attempt is denied and audited.
"""

from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace

import qiki.services.q_core_agent.qiki_orion_intents_service as intents_service
from qiki.shared.nats_subjects import EVENTS_AUDIT


class _FakeNats:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes]] = []

    async def publish(self, subject: str, data: bytes) -> None:
        self.published.append((subject, data))


def _run_handler(payload: dict, *, reply: str = "_INBOX.test") -> _FakeNats:
    nc = _FakeNats()
    msg = SimpleNamespace(data=json.dumps(payload).encode("utf-8"), reply=reply)
    asyncio.run(intents_service._secrets_bus_handler(msg, nc=nc))
    return nc


def test_set_key_over_bus_denied_env_not_set(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    nc = _run_handler({"op": "set_key", "api_key": "sk-injected-over-bus"})

    assert os.getenv("OPENAI_API_KEY") is None

    replies = [data for subject, data in nc.published if subject == "_INBOX.test"]
    assert len(replies) == 1
    reply = json.loads(replies[0])
    assert reply["ok"] is False
    assert reply["error"] == "secret_over_bus_denied"
    assert reply["key_set"] is False


def test_set_key_over_bus_denied_existing_key_untouched(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-original-from-env")

    nc = _run_handler({"op": "set_key", "api_key": "sk-attacker"})

    assert os.environ["OPENAI_API_KEY"] == "sk-original-from-env"
    reply = json.loads([d for s, d in nc.published if s == "_INBOX.test"][0])
    assert reply["ok"] is False
    assert reply["key_set"] is True


def test_set_key_denial_is_audited(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    nc = _run_handler({"op": "set_key", "api_key": "sk-x"})

    audit = [json.loads(d) for s, d in nc.published if s == EVENTS_AUDIT]
    assert len(audit) == 1
    assert audit[0]["event_type"] == "SECRET_OVER_BUS_DENIED"
    assert audit[0]["source"] == "q_core_intents"
    assert "SECRET_OVER_BUS_DENIED" in audit[0]["reason_codes"]
    # The secret itself must never appear in the audit event.
    assert "sk-x" not in json.dumps(audit[0])


def test_status_op_still_reports_key_presence(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-present")

    nc = _run_handler({"op": "status"})

    audit = [d for s, d in nc.published if s == EVENTS_AUDIT]
    assert audit == []
    reply = json.loads([d for s, d in nc.published if s == "_INBOX.test"][0])
    assert reply["ok"] is True
    assert reply["key_set"] is True
