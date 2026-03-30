from __future__ import annotations

from fsm_state_pb2 import FsmStateSnapshot, FSMStateEnum, FSMTransitionStatus
from qiki.services.q_core_agent.core.ship_actuators import PropulsionMode
from qiki.services.q_core_agent.core.ship_fsm_handler import ShipFSMHandler, ShipState


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
        return iter(())

    def get_id(self) -> str:
        return "stub-ship"


class _StubActuatorController:
    def __init__(self, mode: PropulsionMode) -> None:
        self.current_mode = mode

    def emergency_stop(self) -> bool:
        return True


def _snapshot(ship_state_name: str) -> FsmStateSnapshot:
    snap = FsmStateSnapshot()
    snap.current_state = FSMStateEnum.ACTIVE
    snap.context_data["ship_state_name"] = ship_state_name
    return snap


def _set_last_actuation(
    snapshot: FsmStateSnapshot,
    *,
    status: str,
    action: str,
    reason: str = "",
    command_id: str = "cmd-1",
) -> None:
    snapshot.context_data["last_actuation_command_id"] = command_id
    snapshot.context_data["last_actuation_status"] = status
    snapshot.context_data["last_actuation_timestamp"] = "1000.0"
    snapshot.context_data["last_actuation_reason"] = reason
    snapshot.context_data["last_actuation_is_fallback"] = "0"
    snapshot.context_data["last_actuation_action"] = action


def test_accepted_main_drive_keeps_fsm_pending() -> None:
    handler = ShipFSMHandler(_StubShipCore(), _StubActuatorController(mode=PropulsionMode.CRUISE))
    state = _snapshot(ShipState.SHIP_IDLE.value)
    _set_last_actuation(state, status="accepted", action="set_main_drive_thrust")

    next_state = handler.process_fsm_state(state)

    assert next_state.context_data["ship_state_name"] == ShipState.SHIP_IDLE.value
    assert next_state.history[-1].trigger_event == "MAIN_DRIVE_ACCEPTED_PENDING_EXECUTION"
    assert next_state.history[-1].status == FSMTransitionStatus.PENDING


def test_executed_main_drive_allows_cruise_transition() -> None:
    handler = ShipFSMHandler(_StubShipCore(), _StubActuatorController(mode=PropulsionMode.CRUISE))
    state = _snapshot(ShipState.SHIP_IDLE.value)
    _set_last_actuation(state, status="executed", action="set_main_drive_thrust")

    next_state = handler.process_fsm_state(state)

    assert next_state.context_data["ship_state_name"] == ShipState.FLIGHT_CRUISE.value
    assert next_state.history[-1].trigger_event == "MAIN_DRIVE_EXECUTED"
    assert next_state.history[-1].status == FSMTransitionStatus.SUCCESS


def test_timeout_enters_safe_mode() -> None:
    handler = ShipFSMHandler(_StubShipCore(), _StubActuatorController(mode=PropulsionMode.CRUISE))
    state = _snapshot(ShipState.SHIP_IDLE.value)
    _set_last_actuation(state, status="timeout", action="set_main_drive_thrust", reason="timeout")

    next_state = handler.process_fsm_state(state)

    assert next_state.context_data["ship_state_name"] == ShipState.SAFE_MODE.value
    assert next_state.context_data["safe_mode_reason"] == "ACTUATOR_UNAVAILABLE"
    assert next_state.history[-1].trigger_event == "SAFE_MODE_ENTER_ACTUATOR_UNAVAILABLE"


def test_unavailable_enters_safe_mode_with_reason() -> None:
    handler = ShipFSMHandler(_StubShipCore(), _StubActuatorController(mode=PropulsionMode.MANEUVERING))
    state = _snapshot(ShipState.SHIP_IDLE.value)
    _set_last_actuation(state, status="unavailable", action="fire_rcs_thruster:port", reason="link_down")

    next_state = handler.process_fsm_state(state)

    assert next_state.context_data["ship_state_name"] == ShipState.SAFE_MODE.value
    assert next_state.context_data["safe_mode_reason"] == "ACTUATOR_UNAVAILABLE"
    assert next_state.history[-1].trigger_event == "SAFE_MODE_ENTER_ACTUATOR_UNAVAILABLE"


def test_rejected_rcs_stays_idle_and_no_success_transition() -> None:
    handler = ShipFSMHandler(_StubShipCore(), _StubActuatorController(mode=PropulsionMode.MANEUVERING))
    state = _snapshot(ShipState.SHIP_IDLE.value)
    _set_last_actuation(state, status="rejected", action="fire_rcs_thruster:port", reason="invalid")

    next_state = handler.process_fsm_state(state)

    assert next_state.context_data["ship_state_name"] == ShipState.SHIP_IDLE.value
    assert next_state.history[-1].trigger_event == "RCS_COMMAND_REJECTED"
    assert next_state.history[-1].status == FSMTransitionStatus.PENDING
