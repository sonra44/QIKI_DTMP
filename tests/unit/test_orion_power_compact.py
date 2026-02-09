import pytest

from qiki.services.operator_console.main_orion import OrionApp


def _row(key: str, raw: object) -> tuple[str, str, str, object, tuple[str, ...]]:
    return (key, key, str(raw), raw, (f"power.{key}",))


def test_compact_power_rows_keeps_tier_a_even_when_raw_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORION_POWER_COMPACT_DEFAULT", "1")
    app = OrionApp()
    rows = [
        _row("state_of_charge", None),
        _row("load_shedding", None),
        _row("pdu_throttled", None),
        _row("power_input", None),
        _row("power_consumption", None),
        _row("faults", None),
        _row("shed_loads", None),
        _row("dock_temp", None),
    ]

    out = app._compact_power_rows(rows)
    keys = {r[0] for r in out}

    assert "state_of_charge" in keys
    assert "load_shedding" in keys
    assert "pdu_throttled" in keys
    assert "power_input" in keys
    assert "power_consumption" in keys
    assert "faults" in keys
    assert "shed_loads" in keys
    assert "dock_temp" not in keys


def test_compact_power_rows_keeps_non_tier_a_when_signal_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORION_POWER_COMPACT_DEFAULT", "1")
    app = OrionApp()
    rows = [
        _row("state_of_charge", 42.0),
        _row("dock_temp", 55.2),
        _row("dock_power", 0.0),
    ]

    out = app._compact_power_rows(rows)
    keys = {r[0] for r in out}

    assert "state_of_charge" in keys
    assert "dock_temp" in keys
    assert "dock_power" not in keys


def test_compact_power_rows_can_be_disabled_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORION_POWER_COMPACT_DEFAULT", "0")
    app = OrionApp()
    rows = [
        _row("state_of_charge", 99.0),
        _row("dock_temp", None),
        _row("dock_power", 0.0),
    ]

    out = app._compact_power_rows(rows)
    assert [r[0] for r in out] == ["state_of_charge", "dock_temp", "dock_power"]


def test_compact_power_rows_respects_max_rows_and_keeps_tier_a(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORION_POWER_COMPACT_DEFAULT", "1")
    monkeypatch.setenv("ORION_POWER_COMPACT_MAX_ROWS", "8")
    app = OrionApp()
    rows = [
        _row("state_of_charge", 40.0),
        _row("load_shedding", False),
        _row("shed_loads", []),
        _row("faults", []),
        _row("pdu_throttled", False),
        _row("power_input", 200.0),
        _row("power_consumption", 150.0),
        _row("supercap_soc", 55.0),
        _row("dock_connected", True),
        _row("dock_power", 35.0),
    ]

    out = app._compact_power_rows(rows)
    keys = [r[0] for r in out]
    assert len(keys) == 8
    assert keys[:7] == [
        "state_of_charge",
        "faults",
        "pdu_throttled",
        "load_shedding",
        "shed_loads",
        "power_input",
        "power_consumption",
    ]


def test_compact_power_rows_prioritizes_faults_before_nbl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORION_POWER_COMPACT_DEFAULT", "1")
    monkeypatch.setenv("ORION_POWER_COMPACT_MAX_ROWS", "10")
    app = OrionApp()
    rows = [
        _row("state_of_charge", 40.0),
        _row("load_shedding", False),
        _row("nbl_active", True),
        _row("nbl_allowed", True),
        _row("nbl_budget", 50.0),
        _row("nbl_power", 20.0),
        _row("faults", ["PDU_OVERCURRENT"]),
        _row("pdu_throttled", True),
        _row("power_input", 200.0),
        _row("power_consumption", 150.0),
    ]

    out = app._compact_power_rows(rows)
    keys = [r[0] for r in out]
    assert keys.index("faults") < keys.index("nbl_active")
    assert keys.index("pdu_throttled") < keys.index("nbl_active")


def test_compact_power_rows_prioritizes_dock_context_before_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORION_POWER_COMPACT_DEFAULT", "1")
    monkeypatch.setenv("ORION_POWER_COMPACT_MAX_ROWS", "9")
    app = OrionApp()
    rows = [
        _row("state_of_charge", 65.0),
        _row("faults", []),
        _row("pdu_throttled", False),
        _row("load_shedding", False),
        _row("shed_loads", []),
        _row("power_input", 210.0),
        _row("power_consumption", 180.0),
        _row("dock_connected", True),
        _row("dock_power", 25.0),
        _row("bus_voltage", 28.0),
        _row("bus_current", 8.0),
    ]

    out = app._compact_power_rows(rows)
    keys = [r[0] for r in out]
    assert len(keys) == 9
    assert keys[7] == "dock_connected"
    assert keys[8] == "dock_power"
    assert "bus_voltage" not in keys
