from __future__ import annotations

from qiki.services.operator_console.main_orion import OrionApp


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
