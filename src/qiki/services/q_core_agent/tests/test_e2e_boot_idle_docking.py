from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from fsm_state_pb2 import FSMStateEnum, FsmStateSnapshot
from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.ship_actuators import (
    ActuationResult,
    ActuationStatus,
    ShipActuatorController,
    ThrusterAxis,
)
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


class _ScenarioShipCore:
    def __init__(self) -> None:
        self._readings: list[SensorReading] = []

    def set_readings(self, readings: list[SensorReading]) -> None:
        self._readings = readings

    def iter_latest_sensor_readings(self):
        yield from self._readings

    def send_actuator_command(self, _command: Any) -> None:
        return None

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

    def get_id(self) -> str:
        return "e2e-ship"


class _DeterministicActuatorController(ShipActuatorController):
    def __init__(self, ship_core: _ScenarioShipCore, *, event_store: EventStore) -> None:
        super().__init__(ship_core, event_store=event_store)
        self._forced_status: dict[str, ActuationStatus] = {}

    def force_status(self, action: str, status: ActuationStatus) -> None:
        self._forced_status[action] = status

    def _dispatch_command(self, command: Any, *, action: str) -> ActuationResult:  # noqa: D401
        forced = self._forced_status.get(action)
        if forced is None:
            return super()._dispatch_command(command, action=action)
        command_id = self._set_command_id(command)
        return self._build_actuation_result(
            status=forced,
            reason=f"FORCED_{forced.name}",
            command_id=command_id,
            correlation_id=command_id,
            action=action,
            is_fallback=False,
        )


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


def _state(snapshot: FsmStateSnapshot) -> str:
    return str(snapshot.context_data.get("ship_state_name", ""))


def test_e2e_boot_idle_maneuvering_docking_event_trace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("QIKI_DOCKING_CONFIRMATION_COUNT", "3")
    monkeypatch.setenv("QIKI_SENSOR_MAX_AGE_S", "2.0")
    monkeypatch.setenv("QIKI_SENSOR_MIN_QUALITY", "0.5")
    monkeypatch.setenv("QIKI_EVENT_STORE_ENABLE", "true")

    event_store = EventStore(enabled=True, maxlen=1000)
    ship_core = _ScenarioShipCore()
    actuator = _DeterministicActuatorController(ship_core, event_store=event_store)
    handler = ShipFSMHandler(ship_core, actuator, event_store=event_store)

    fsm = FsmStateSnapshot()
    fsm.current_state = FSMStateEnum.BOOTING
    fsm.context_data["ship_state_name"] = ShipState.SHIP_STARTUP.value

    ship_core.set_readings([])
    fsm = handler.process_fsm_state(fsm)
    assert _state(fsm) == ShipState.SHIP_IDLE.value

    actuator.force_status("set_main_drive_thrust", ActuationStatus.ACCEPTED)
    accepted = actuator.set_main_drive_thrust_result(thrust_percent=20.0, duration_sec=1.0)
    assert accepted.status == ActuationStatus.ACCEPTED
    fsm = handler.process_fsm_state(fsm)
    assert _state(fsm) == ShipState.SHIP_IDLE.value
    assert fsm.history[-1].trigger_event == "MAIN_DRIVE_ACCEPTED_PENDING_EXECUTION"

    actuator.force_status("fire_rcs_thruster:port", ActuationStatus.EXECUTED)
    executed = actuator.fire_rcs_thruster_result(
        thruster_axis=ThrusterAxis.PORT,
        thrust_percent=30.0,
        duration_sec=1.0,
    )
    assert executed.status == ActuationStatus.EXECUTED

    ship_core.set_readings([_station_track_reading(range_m=120.0, vr_mps=0.4, quality=0.95)])
    fsm = handler.process_fsm_state(fsm)
    assert _state(fsm) == ShipState.FLIGHT_MANEUVERING.value

    ship_core.set_readings([_station_track_reading(range_m=40.0, vr_mps=0.3, quality=0.95)])
    fsm = handler.process_fsm_state(fsm)
    assert _state(fsm) == ShipState.DOCKING_APPROACH.value

    for _ in range(2):
        ship_core.set_readings([_station_track_reading(range_m=10.0, vr_mps=0.1, quality=0.95)])
        fsm = handler.process_fsm_state(fsm)
        assert _state(fsm) == ShipState.DOCKING_APPROACH.value

    ship_core.set_readings([_station_track_reading(range_m=9.0, vr_mps=0.1, quality=0.95)])
    fsm = handler.process_fsm_state(fsm)
    assert _state(fsm) == ShipState.DOCKING_ENGAGED.value

    all_events = event_store.recent(500)
    assert all_events

    fsm_events = [e for e in all_events if e.subsystem == "FSM" and e.event_type == "FSM_TRANSITION"]
    actuation_events = [e for e in all_events if e.subsystem == "ACTUATORS" and e.event_type == "ACTUATION_RECEIPT"]
    sensor_events = [e for e in all_events if e.subsystem == "SENSORS" and e.event_type == "SENSOR_TRUST_VERDICT"]
    safe_mode_events = [e for e in all_events if e.subsystem == "SAFE_MODE" and e.event_type == "SAFE_MODE"]

    assert len(fsm_events) >= 1
    assert len(actuation_events) >= 2
    assert len(sensor_events) >= 1
    assert not safe_mode_events

    assert any(e.payload.get("status") == "accepted" for e in actuation_events)
    assert any(e.payload.get("status") == "executed" for e in actuation_events)
    assert any(e.payload.get("reason") == "OK" for e in sensor_events)

    artifact_path = tmp_path / "artifacts" / "e2e_task_0013_events.jsonl"
    exported = event_store.export_jsonl(str(artifact_path))
    assert exported >= 1
    assert artifact_path.exists()

    with artifact_path.open("r", encoding="utf-8") as handle:
        first_line = handle.readline().strip()
    assert first_line
    first_event = json.loads(first_line)
    assert {"event_id", "ts", "subsystem", "event_type", "reason", "truth_state"} <= set(first_event.keys())
