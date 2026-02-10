from __future__ import annotations

import math
import time

import pytest

from fsm_state_pb2 import FsmStateSnapshot, FSMStateEnum, FSMTransitionStatus
from qiki.services.q_core_agent.core.ship_actuators import PropulsionMode
from qiki.services.q_core_agent.core.ship_fsm_handler import ShipFSMHandler, ShipState
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

    def iter_latest_sensor_readings(self):
        yield from self._readings

    def get_id(self) -> str:
        return "stub-ship"


class _StubActuatorController:
    def __init__(self) -> None:
        self.current_mode = PropulsionMode.MANEUVERING

    def emergency_stop(self) -> bool:
        return True


def _snapshot_with_ship_state(ship_state_name: str) -> FsmStateSnapshot:
    snap = FsmStateSnapshot()
    snap.current_state = FSMStateEnum.ACTIVE
    snap.context_data["ship_state_name"] = ship_state_name
    return snap


def _station_track_reading(range_m: float, vr_mps: float, *, quality: float = 0.9, age_s: float = 0.0) -> SensorReading:
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


def _step(handler: ShipFSMHandler, state: FsmStateSnapshot) -> FsmStateSnapshot:
    return handler.process_fsm_state(state)


def test_docking_engaged_requires_three_consecutive_valid_cycles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_DOCKING_CONFIRMATION_COUNT", "3")
    monkeypatch.setenv("QIKI_SENSOR_MAX_AGE_S", "2.0")
    monkeypatch.setenv("QIKI_SENSOR_MIN_QUALITY", "0.5")
    ship_core = _StubShipCore([_station_track_reading(range_m=10.0, vr_mps=0.1)])
    handler = ShipFSMHandler(ship_core, _StubActuatorController())

    state = _snapshot_with_ship_state(ShipState.DOCKING_APPROACH.value)
    state = _step(handler, state)
    assert state.context_data["ship_state_name"] == ShipState.DOCKING_APPROACH.value
    assert state.context_data["docking_confirm_hits"] == "1"
    assert state.history[-1].trigger_event == "DOCKING_CONFIRMING_1_OF_3"
    assert state.history[-1].status == FSMTransitionStatus.PENDING

    state = _step(handler, state)
    assert state.context_data["ship_state_name"] == ShipState.DOCKING_APPROACH.value
    assert state.context_data["docking_confirm_hits"] == "2"
    assert state.history[-1].trigger_event == "DOCKING_CONFIRMING_2_OF_3"

    state = _step(handler, state)
    assert state.context_data["ship_state_name"] == ShipState.DOCKING_ENGAGED.value
    assert state.history[-1].trigger_event == "DOCKING_CONFIRMED"
    assert state.history[-1].status == FSMTransitionStatus.SUCCESS


def test_docking_target_lost_does_not_transition_to_engaged() -> None:
    ship_core = _StubShipCore([])
    handler = ShipFSMHandler(ship_core, _StubActuatorController())

    state = _snapshot_with_ship_state(ShipState.DOCKING_APPROACH.value)
    next_state = _step(handler, state)

    assert next_state.context_data["ship_state_name"] == ShipState.FLIGHT_MANEUVERING.value
    assert next_state.history[-1].trigger_event == "DOCKING_TARGET_LOST"


def test_stale_track_does_not_increase_confirmation_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_SENSOR_MAX_AGE_S", "2.0")
    ship_core = _StubShipCore([_station_track_reading(range_m=10.0, vr_mps=0.1, age_s=20.0)])
    handler = ShipFSMHandler(ship_core, _StubActuatorController())

    state = _snapshot_with_ship_state(ShipState.DOCKING_APPROACH.value)
    next_state = _step(handler, state)

    assert next_state.context_data["ship_state_name"] == ShipState.DOCKING_APPROACH.value
    assert next_state.context_data["docking_confirm_hits"] == "0"
    assert next_state.history[-1].trigger_event == "DOCKING_SENSOR_VALIDATION_FAILED"


def test_invalid_values_do_not_confirm_docking() -> None:
    ship_core = _StubShipCore([_station_track_reading(range_m=-1.0, vr_mps=math.nan)])
    handler = ShipFSMHandler(ship_core, _StubActuatorController())

    state = _snapshot_with_ship_state(ShipState.DOCKING_APPROACH.value)
    next_state = _step(handler, state)

    assert next_state.context_data["ship_state_name"] == ShipState.FLIGHT_MANEUVERING.value
    assert next_state.history[-1].trigger_event == "DOCKING_TARGET_LOST"


def test_flapping_resets_confirmation_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_DOCKING_CONFIRMATION_COUNT", "3")
    ship_core = _StubShipCore([_station_track_reading(range_m=10.0, vr_mps=0.1)])
    handler = ShipFSMHandler(ship_core, _StubActuatorController())
    state = _snapshot_with_ship_state(ShipState.DOCKING_APPROACH.value)

    state = _step(handler, state)
    assert state.context_data["docking_confirm_hits"] == "1"

    ship_core.set_readings([_station_track_reading(range_m=10.0, vr_mps=0.1, quality=0.1)])
    state = _step(handler, state)
    assert state.context_data["docking_confirm_hits"] == "0"
    assert state.context_data["ship_state_name"] == ShipState.DOCKING_APPROACH.value

    ship_core.set_readings([_station_track_reading(range_m=10.0, vr_mps=0.1)])
    state = _step(handler, state)
    assert state.context_data["docking_confirm_hits"] == "1"
    assert state.context_data["ship_state_name"] == ShipState.DOCKING_APPROACH.value
