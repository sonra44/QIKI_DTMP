from __future__ import annotations
from __future__ import annotations

from qiki.services.q_core_agent.core.ship_actuators import PropulsionMode
from qiki.services.q_core_agent.core.ship_fsm_handler import ShipFSMHandler, ShipState

from fsm_state_pb2 import FsmStateSnapshot, FSMStateEnum, FSMTransitionStatus
from radar.v1 import radar_pb2
from sensor_raw_in_pb2 import SensorReading
import time
import pytest


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


def _station_track_reading(range_m: float, vr_mps: float) -> SensorReading:
    track = radar_pb2.RadarTrack()
    track.object_type = radar_pb2.ObjectType.STATION
    track.range_m = float(range_m)
    track.vr_mps = float(vr_mps)
    track.quality = 0.9
    ts_now = time.time()
    track.timestamp.seconds = int(ts_now)
    track.timestamp.nanos = int((ts_now - int(ts_now)) * 1_000_000_000)

    reading = SensorReading()
    reading.radar_track.CopyFrom(track)
    return reading


def test_docking_approach_transitions_to_engaged_when_docked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_DOCKING_CONFIRMATION_COUNT", "1")
    ship_core = _StubShipCore([_station_track_reading(range_m=10.0, vr_mps=0.1)])
    actuator_controller = _StubActuatorController()
    handler = ShipFSMHandler(ship_core, actuator_controller)

    current = _snapshot_with_ship_state(ShipState.DOCKING_APPROACH.value)
    next_state = handler.process_fsm_state(current)

    assert next_state.context_data["ship_state_name"] == ShipState.DOCKING_ENGAGED.value
    assert next_state.current_state == FSMStateEnum.ACTIVE
    assert len(next_state.history) == 1
    assert next_state.history[0].trigger_event == "DOCKING_CONFIRMED"
    assert next_state.history[0].status == FSMTransitionStatus.SUCCESS


def test_docking_approach_returns_to_maneuvering_when_target_lost() -> None:
    ship_core = _StubShipCore([])
    actuator_controller = _StubActuatorController()
    handler = ShipFSMHandler(ship_core, actuator_controller)

    current = _snapshot_with_ship_state(ShipState.DOCKING_APPROACH.value)
    next_state = handler.process_fsm_state(current)

    assert next_state.context_data["ship_state_name"] == ShipState.FLIGHT_MANEUVERING.value
    assert next_state.current_state == FSMStateEnum.ACTIVE
    assert len(next_state.history) == 1
    assert next_state.history[0].trigger_event == "DOCKING_TARGET_LOST"
