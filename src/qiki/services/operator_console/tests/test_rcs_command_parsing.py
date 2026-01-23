from __future__ import annotations

from qiki.services.operator_console.main_orion import OrionApp


def test_parse_rcs_stop() -> None:
    parsed = OrionApp._parse_rcs_cli_command("rcs.stop")
    assert parsed == {"kind": "stop"}


def test_parse_rcs_fire_defaults_duration() -> None:
    parsed = OrionApp._parse_rcs_cli_command("rcs.port 30")
    assert parsed is not None
    assert parsed["kind"] == "fire"
    assert parsed["axis"] == "port"
    assert parsed["pct"] == 30.0
    assert parsed["duration_s"] == 1.0


def test_parse_rcs_fire_with_duration() -> None:
    parsed = OrionApp._parse_rcs_cli_command("rcs.up 5 250ms")
    assert parsed is not None
    assert parsed["kind"] == "fire"
    assert parsed["axis"] == "up"
    assert parsed["pct"] == 5.0
    assert abs(float(parsed["duration_s"]) - 0.25) < 1e-9


def test_parse_rcs_invalid() -> None:
    assert OrionApp._parse_rcs_cli_command("rcs") is None
    assert OrionApp._parse_rcs_cli_command("rcs.side 10") is None
    assert OrionApp._parse_rcs_cli_command("rcs.port xx") is None
    assert OrionApp._parse_rcs_cli_command("rcs.port 10 0s") is None

