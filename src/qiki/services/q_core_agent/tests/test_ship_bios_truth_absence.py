import pytest

from qiki.services.q_core_agent.core import ship_bios_handler as sbh
from qiki.services.q_core_agent.core.ship_core import (
    ComputingStatus,
    HullStatus,
    LifeSupportStatus,
    PowerSystemStatus,
    PropulsionStatus,
    SensorStatus,
)


class _ShipCoreOK:
    def __init__(self) -> None:
        self._config = {"mode": "normal"}

    def get_hull_status(self) -> HullStatus:
        return HullStatus(
            integrity=98.0,
            max_integrity=100.0,
            mass_kg=1000.0,
            volume_m3=10.0,
            compartments={"bridge": {"pressure": 1.0, "temperature": 295.0}},
        )

    def get_power_status(self) -> PowerSystemStatus:
        return PowerSystemStatus(
            reactor_output_mw=80.0,
            reactor_max_output_mw=100.0,
            reactor_fuel_hours=48.0,
            reactor_temperature_k=2800.0,
            battery_charge_mwh=80.0,
            battery_capacity_mwh=100.0,
            power_distribution={},
        )

    def get_propulsion_status(self) -> PropulsionStatus:
        return PropulsionStatus(
            main_drive_thrust_n=0.0,
            main_drive_max_thrust_n=100.0,
            main_drive_fuel_kg=120.0,
            main_drive_status="ready",
            rcs_status={"thruster_1": {"status": "ready", "fuel_kg": 10.0}},
        )

    def get_sensor_status(self) -> SensorStatus:
        return SensorStatus(
            active_sensors=["long_range_radar", "navigation_computer"],
            sensor_data={
                "long_range_radar": {"status": "online"},
                "navigation_computer": {"status": "online"},
            },
            total_power_consumption_kw=100.0,
        )

    def get_life_support_status(self) -> LifeSupportStatus:
        return LifeSupportStatus(
            atmosphere={"oxygen_percent": 21.0, "co2_ppm": 450.0, "pressure_kpa": 101.0},
            water_recycling={"recycling_efficiency": 0.95},
            air_recycling={},
        )

    def get_computing_status(self) -> ComputingStatus:
        return ComputingStatus(
            qiki_core_status="active",
            qiki_temperature_k=295.0,
            qiki_power_consumption_kw=10.0,
            backup_systems={"life_support_backup": "standby"},
        )


class _ShipCoreTimeout(_ShipCoreOK):
    def get_hull_status(self) -> HullStatus:
        raise TimeoutError("bios timeout")


class _ShipCoreUnavailable(_ShipCoreOK):
    def get_hull_status(self) -> HullStatus:
        raise ConnectionError("bios unavailable")


def test_bios_happy_path_returns_valid_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_ALLOW_BIOS_FALLBACK", "false")
    monkeypatch.setattr(sbh, "BIOS_PROTO_FALLBACK_ACTIVE", False)

    handler = sbh.ShipBiosHandler(_ShipCoreOK())
    source = sbh.BiosStatusReport()
    result = handler.process_bios_status_result(source)

    assert result.ok is True
    assert result.reason == sbh.BiosReason.OK.value
    assert result.report is not None
    assert hasattr(result.report, "all_systems_go")


def test_bios_timeout_returns_explicit_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_ALLOW_BIOS_FALLBACK", "false")
    monkeypatch.setattr(sbh, "BIOS_PROTO_FALLBACK_ACTIVE", False)

    handler = sbh.ShipBiosHandler(_ShipCoreTimeout())
    result = handler.process_bios_status_result(sbh.BiosStatusReport())

    assert result.ok is False
    assert result.report is None
    assert result.reason == sbh.BiosReason.TIMEOUT.value


def test_bios_unavailable_returns_explicit_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_ALLOW_BIOS_FALLBACK", "false")
    monkeypatch.setattr(sbh, "BIOS_PROTO_FALLBACK_ACTIVE", False)

    handler = sbh.ShipBiosHandler(_ShipCoreUnavailable())
    result = handler.process_bios_status_result(sbh.BiosStatusReport())

    assert result.ok is False
    assert result.report is None
    assert result.reason == sbh.BiosReason.UNAVAILABLE.value


def test_invalid_report_is_rejected_as_non_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_ALLOW_BIOS_FALLBACK", "false")
    monkeypatch.setattr(sbh, "BIOS_PROTO_FALLBACK_ACTIVE", False)

    handler = sbh.ShipBiosHandler(_ShipCoreOK())

    class _InvalidReport:
        def __init__(self) -> None:
            self.post_results = []
            self.all_systems_go = True

    monkeypatch.setattr(handler, "_build_bios_report", lambda _source: _InvalidReport())
    result = handler.process_bios_status_result(sbh.BiosStatusReport())

    assert result.ok is False
    assert result.report is None
    assert result.reason.startswith(sbh.BiosReason.INVALID_REPORT.value)


def test_fallback_allowed_marks_result_and_non_green(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_ALLOW_BIOS_FALLBACK", "true")
    monkeypatch.setattr(sbh, "BIOS_PROTO_FALLBACK_ACTIVE", True)

    handler = sbh.ShipBiosHandler(_ShipCoreOK())
    result = handler.process_bios_status_result(sbh.BiosStatusReport())

    assert result.ok is True
    assert result.is_fallback is True
    assert result.reason == sbh.BiosReason.SIMULATED.value
    assert result.report is not None
    assert getattr(result.report, "all_systems_go") is False
