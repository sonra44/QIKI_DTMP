from qiki.services.operator_console.main_orion import OrionApp


def test_parse_dock_release() -> None:
    parsed = OrionApp._parse_docking_cli_command("dock.release")
    assert parsed == {"kind": "release"}


def test_parse_dock_engage_default_port() -> None:
    parsed = OrionApp._parse_docking_cli_command("dock.engage")
    assert parsed == {"kind": "engage", "port": None}


def test_parse_dock_engage_with_port() -> None:
    parsed = OrionApp._parse_docking_cli_command("dock.engage B")
    assert parsed == {"kind": "engage", "port": "B"}


def test_parse_dock_invalid() -> None:
    assert OrionApp._parse_docking_cli_command("dock") is None
    assert OrionApp._parse_docking_cli_command("dock.engage   ") == {"kind": "engage", "port": None}
    assert OrionApp._parse_docking_cli_command("dock.release now") is None

