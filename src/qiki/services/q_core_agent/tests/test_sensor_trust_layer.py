from __future__ import annotations

import math
import time

import pytest

from fsm_state_pb2 import FSMStateEnum, FsmStateSnapshot
from qiki.services.q_core_agent.core.ship_actuators import PropulsionMode
from qiki.services.q_core_agent.core.ship_fsm_handler import (
    SensorTrustReason,
    ShipContext,
    ShipFSMHandler,
    ShipState,
    TrustedSensorFrame,
)
from radar.v1 import radar_pb2
from sensor_raw_in_pb2 import SensorReading


class _HullStatus:
    integrity = 100.0


class _PowerStatus:
    reactor_output_mw = 10.0
    battery_charge_mwh = 10.0


class _LifeSupportStatus:
    atmosphere = {"oxygen_percent": 21, "co2_ppm": 400}


class _ComputingStatus:
    qiki_core_status = "active"


class _SensorStatus:
    def __init__(self, active_sensors: list[str]) -> None:
        self.active_sensors = active_sensors


class _PropulsionStatus:
    main_drive_status = "ready"
    main_drive_fuel_kg = 100.0


class _StubShipCore:
    def __init__(self, readings: list[SensorReading]) -> None:
        self._readings = readings

    def set_readings(self, readings: list[SensorReading]) -> None:
        self._readings = readings

    def iter_latest_sensor_readings(self):
        yield from self._readings

    def get_hull_status(self) -> _HullStatus:
        return _HullStatus()

    def get_power_status(self) -> _PowerStatus:
        return _PowerStatus()

    def get_life_support_status(self) -> _LifeSupportStatus:
        return _LifeSupportStatus()

    def get_computing_status(self) -> _ComputingStatus:
        return _ComputingStatus()

    def get_sensor_status(self) -> _SensorStatus:
        return _SensorStatus(active_sensors=["long_range_radar", "navigation_computer"])

    def get_propulsion_status(self) -> _PropulsionStatus:
        return _PropulsionStatus()


class _StubActuatorController:
    def __init__(self, mode: PropulsionMode = PropulsionMode.IDLE) -> None:
        self.current_mode = mode

    def emergency_stop(self) -> bool:
        return True


def _station_track_reading(
    range_m: float,
    vr_mps: float,
    *,
    quality: float = 0.9,
    age_s: float = 0.0,
) -> SensorReading:
    track = radar_pb2.RadarTrack()
    track.object_type = radar_pb2.ObjectType.STATION
    track.range_m = float(range_m)
    track.vr_mps = float(vr_mps)
    track.quality = float(quality)
    ts_now = time.time() - age_s
    track.timestamp.seconds = int(ts_now)
    track.timestamp.nanos = int((ts_now - int(ts_now)) * 1_000_000_000)

    reading = SensorReading()
    reading.radar_track.CopyFrom(track)
    return reading


def _context(readings: list[SensorReading]) -> ShipContext:
    return ShipContext(_StubShipCore(readings), _StubActuatorController())


def test_sensor_trust_no_data() -> None:
    trusted = _context([]).get_trusted_station_track()

    assert trusted.ok is False
    assert trusted.reason == SensorTrustReason.NO_DATA
    assert trusted.data is None


def test_sensor_trust_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_SENSOR_MAX_AGE_S", "2.0")
    trusted = _context([_station_track_reading(range_m=10.0, vr_mps=0.1, age_s=12.0)]).get_trusted_station_track()

    assert trusted.ok is False
    assert trusted.reason == SensorTrustReason.STALE
    assert trusted.age_s is not None
    assert trusted.age_s > 2.0


def test_sensor_trust_low_quality(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_SENSOR_MIN_QUALITY", "0.5")
    trusted = _context([_station_track_reading(range_m=10.0, vr_mps=0.1, quality=0.2)]).get_trusted_station_track()

    assert trusted.ok is False
    assert trusted.reason == SensorTrustReason.LOW_QUALITY
    assert trusted.quality == pytest.approx(0.2)


def test_sensor_trust_invalid_values() -> None:
    trusted = _context([_station_track_reading(range_m=-1.0, vr_mps=math.nan)]).get_trusted_station_track()

    assert trusted.ok is False
    assert trusted.reason == SensorTrustReason.NO_DATA


def test_sensor_trust_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_SENSOR_MAX_AGE_S", "2.0")
    monkeypatch.setenv("QIKI_SENSOR_MIN_QUALITY", "0.5")
    trusted = _context([_station_track_reading(range_m=15.0, vr_mps=0.1, quality=0.9)]).get_trusted_station_track()

    assert trusted.ok is True
    assert trusted.reason == SensorTrustReason.OK
    assert trusted.data is not None
    assert trusted.data["range_m"] == pytest.approx(15.0)
    assert trusted.data["vr_mps"] == pytest.approx(0.1)
    assert trusted.age_s is not None
    assert trusted.quality == pytest.approx(0.9)


def test_fsm_uses_trusted_frame_not_raw(monkeypatch: pytest.MonkeyPatch) -> None:
    ship_core = _StubShipCore([_station_track_reading(range_m=100.0, vr_mps=0.1)])
    handler = ShipFSMHandler(ship_core, _StubActuatorController(mode=PropulsionMode.IDLE))

    monkeypatch.setattr(
        handler.ship_context,
        "get_trusted_station_track",
        lambda: TrustedSensorFrame(ok=False, reason=SensorTrustReason.NO_DATA),
    )

    state = FsmStateSnapshot()
    state.current_state = FSMStateEnum.IDLE
    state.context_data["ship_state_name"] = ShipState.SHIP_IDLE.value

    next_state = handler.process_fsm_state(state)

    assert next_state.context_data["ship_state_name"] == ShipState.SHIP_IDLE.value
    assert all("DOCKING_TARGET" not in tr.trigger_event for tr in next_state.history)
