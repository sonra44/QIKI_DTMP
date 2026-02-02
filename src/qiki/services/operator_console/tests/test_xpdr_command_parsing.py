from __future__ import annotations

from qiki.services.operator_console.main_orion import OrionApp


def test_parse_xpdr_mode() -> None:
    parsed = OrionApp._parse_xpdr_cli_command("xpdr.mode silent")
    assert parsed == {"mode": "SILENT"}


def test_parse_xpdr_mode_case_insensitive() -> None:
    parsed = OrionApp._parse_xpdr_cli_command("XPDR.MODE Spoof")
    assert parsed == {"mode": "SPOOF"}


def test_parse_xpdr_mode_ru_alias() -> None:
    parsed = OrionApp._parse_xpdr_cli_command("ответчик.режим on")
    assert parsed == {"mode": "ON"}


def test_parse_xpdr_mode_ru_head_variant() -> None:
    parsed = OrionApp._parse_xpdr_cli_command("xpdr.режим off")
    assert parsed == {"mode": "OFF"}


def test_parse_xpdr_invalid() -> None:
    assert OrionApp._parse_xpdr_cli_command("xpdr") is None
    assert OrionApp._parse_xpdr_cli_command("xpdr.mode") is None
    assert OrionApp._parse_xpdr_cli_command("xpdr.mode maybe") is None
    assert OrionApp._parse_xpdr_cli_command("ответчик.режим maybe") is None
