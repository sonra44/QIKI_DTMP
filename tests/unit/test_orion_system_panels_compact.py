import pytest

from qiki.services.operator_console.main_orion import I18N, OrionApp


def _row(key: str, value: str) -> tuple[str, str, str]:
    return (key, key, value)


def test_system_compact_keeps_essential_and_signal_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORION_SYSTEM_COMPACT_DEFAULT", "1")
    app = OrionApp()
    rows = [
        _row("link", I18N.NA),
        _row("age", I18N.NA),
        _row("velocity", "2.0 m/s"),
        _row("debug_noise", I18N.NA),
        _row("thermal_hint", "21.0 C"),
    ]

    out = app._compact_system_panel_rows(rows, essential_keys={"link", "age"}, max_rows=6)
    keys = [r[0] for r in out]
    assert "link" in keys
    assert "age" in keys
    assert "velocity" in keys
    assert "thermal_hint" in keys
    assert "debug_noise" not in keys


def test_system_compact_respects_max_rows_with_essential_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORION_SYSTEM_COMPACT_DEFAULT", "1")
    app = OrionApp()
    rows = [
        _row("link", I18N.NA),
        _row("age", I18N.NA),
        _row("velocity", "1"),
        _row("heading", "90"),
        _row("position", "0,0,0"),
    ]

    out = app._compact_system_panel_rows(rows, essential_keys={"link", "age", "velocity"}, max_rows=3)
    assert [r[0] for r in out] == ["link", "age", "velocity"]


def test_system_compact_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORION_SYSTEM_COMPACT_DEFAULT", "0")
    app = OrionApp()
    rows = [
        _row("link", I18N.NA),
        _row("age", I18N.NA),
        _row("noise", I18N.NA),
    ]

    out = app._compact_system_panel_rows(rows, essential_keys={"link"}, max_rows=2)
    assert out == rows
