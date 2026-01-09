from __future__ import annotations

import asyncio

import pytest

from qiki.services.operator_console.main_orion import OrionApp
from qiki.shared.models.orion_qiki_protocol import IntentV1
from qiki.shared.nats_subjects import QIKI_INTENT_V1


def test_parse_qiki_intent_prefix_q_colon() -> None:
    is_qiki, text = OrionApp._parse_qiki_intent("q: scan 360")
    assert is_qiki is True
    assert text == "scan 360"


def test_parse_qiki_intent_prefix_double_slash() -> None:
    is_qiki, text = OrionApp._parse_qiki_intent("// scan 360")
    assert is_qiki is True
    assert text == "scan 360"


def test_parse_qiki_intent_empty_payload() -> None:
    is_qiki, text = OrionApp._parse_qiki_intent("q:")
    assert is_qiki is True
    assert text is None


def test_parse_qiki_intent_shell_command() -> None:
    is_qiki, text = OrionApp._parse_qiki_intent("clear")
    assert is_qiki is False
    assert text is None


class _FakeNats:
    def __init__(self) -> None:
        """
        Initialize the fake NATS publisher and prepare an empty list of captured publishes.
        
        The `published` attribute records published messages as a list of tuples (subject, payload),
        where `subject` is a string and `payload` is a dict representing the published command.
        """
        self.published: list[tuple[str, dict]] = []

    async def publish_command(self, subject: str, command: dict) -> None:
        """
        Record a published command by appending the (subject, command) tuple to the `published` list.
        
        Parameters:
            subject (str): NATS subject under which the command was published.
            command (dict): Payload of the published command.
        
        """
        self.published.append((subject, command))


@pytest.mark.asyncio
async def test_qiki_prefix_publishes_intent_v1() -> None:
    app = OrionApp()
    app.nats_client = _FakeNats()  # type: ignore[assignment]

    await app._run_command("q: scan 360")
    await asyncio.sleep(0)

    assert len(app.nats_client.published) == 1  # type: ignore[attr-defined]
    subject, payload = app.nats_client.published[0]  # type: ignore[attr-defined]
    assert subject == QIKI_INTENT_V1

    intent = IntentV1.model_validate(payload)
    assert intent.environment_mode is not None
    assert intent.screen


@pytest.mark.asyncio
async def test_shell_command_does_not_publish_intent() -> None:
    app = OrionApp()
    app.nats_client = _FakeNats()  # type: ignore[assignment]

    await app._run_command("help")
    await asyncio.sleep(0)

    assert app.nats_client.published == []  # type: ignore[attr-defined]