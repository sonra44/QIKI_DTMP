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
    def __init__(self) -> None:
        self._active_sensors = ["long_range_radar", "navigation_computer"]

    def set_sensors(self, active_sensors: list[str]) -> None:
        self._active_sensors = active_sensors

    def get_hull_status(self) -> _HullStatus:
        return _HullStatus()

    def get_power_status(self) -> _PowerStatus:
        return _PowerStatus()

    def get_life_support_status(self) -> _LifeSupportStatus:
        return _LifeSupportStatus()

    def get_computing_status(self) -> _ComputingStatus:
        return _ComputingStatus()

    def get_sensor_status(self) -> _SensorStatus:
        return _SensorStatus(active_sensors=self._active_sensors)

    def get_propulsion_status(self) -> _PropulsionStatus:
        return _PropulsionStatus()

    def iter_latest_sensor_readings(self):
        return iter(())

    def get_id(self) -> str:
        return "stub-safe-mode-ship"


class _StubActuatorController:
    def __init__(self) -> None:
        self.current_mode = PropulsionMode.CRUISE
        self.emergency_stop_calls = 0

    def emergency_stop(self) -> bool:
        self.emergency_stop_calls += 1
        return True


def _snapshot_with_ship_state(ship_state_name: str) -> FsmStateSnapshot:
    snap = FsmStateSnapshot()
    snap.current_state = FSMStateEnum.ERROR_STATE if ship_state_name == ShipState.SAFE_MODE.value else FSMStateEnum.ACTIVE
    snap.context_data["ship_state_name"] = ship_state_name
    return snap


def test_safe_mode_enters_on_bios_unavailable() -> None:
    ship_core = _StubShipCore()
    actuator = _StubActuatorController()
    handler = ShipFSMHandler(ship_core, actuator)
    state = _snapshot_with_ship_state(ShipState.FLIGHT_CRUISE.value)
    state.context_data["safe_bios_ok"] = "0"

    next_state = handler.process_fsm_state(state)

    assert next_state.context_data["ship_state_name"] == ShipState.SAFE_MODE.value
    assert next_state.context_data["safe_mode_reason"] == "BIOS_UNAVAILABLE"
    assert next_state.history[-1].trigger_event == "SAFE_MODE_ENTER_BIOS_UNAVAILABLE"
    assert next_state.history[-1].status == FSMTransitionStatus.SUCCESS


def test_safe_mode_enters_on_sensors_stale_reason_request() -> None:
    ship_core = _StubShipCore()
    actuator = _StubActuatorController()
    handler = ShipFSMHandler(ship_core, actuator)
    state = _snapshot_with_ship_state(ShipState.SHIP_IDLE.value)
    state.context_data["safe_mode_request_reason"] = "SENSORS_STALE"

    next_state = handler.process_fsm_state(state)

    assert next_state.context_data["ship_state_name"] == ShipState.SAFE_MODE.value
    assert next_state.context_data["safe_mode_reason"] == "SENSORS_STALE"
    assert next_state.history[-1].trigger_event == "SAFE_MODE_ENTER_SENSORS_STALE"


def test_safe_mode_blocks_transition_to_active_state() -> None:
    ship_core = _StubShipCore()
    actuator = _StubActuatorController()
    handler = ShipFSMHandler(ship_core, actuator)
    state = _snapshot_with_ship_state(ShipState.SAFE_MODE.value)
    state.context_data["safe_mode_reason"] = "PROVIDER_UNAVAILABLE"
    state.context_data["safe_provider_ok"] = "0"
    state.context_data["safe_bios_ok"] = "1"
    state.context_data["safe_sensors_ok"] = "1"

    next_state = handler.process_fsm_state(state)

    assert next_state.context_data["ship_state_name"] == ShipState.SAFE_MODE.value
    assert next_state.history[-1].trigger_event == "SAFE_MODE_HOLD_PROVIDER_UNAVAILABLE"
    assert next_state.history[-1].status == FSMTransitionStatus.PENDING


def test_safe_mode_exits_after_n_consecutive_valid_cycles(monkeypatch) -> None:
    monkeypatch.setenv("QIKI_SAFE_EXIT_CONFIRMATION_COUNT", "3")
    ship_core = _StubShipCore()
    actuator = _StubActuatorController()
    handler = ShipFSMHandler(ship_core, actuator)
    state = _snapshot_with_ship_state(ShipState.SAFE_MODE.value)
    state.context_data["safe_mode_reason"] = "BIOS_UNAVAILABLE"
    state.context_data["safe_bios_ok"] = "1"
    state.context_data["safe_sensors_ok"] = "1"
    state.context_data["safe_provider_ok"] = "1"

    state = handler.process_fsm_state(state)
    assert state.context_data["ship_state_name"] == ShipState.SAFE_MODE.value
    assert state.context_data["safe_mode_exit_hits"] == "1"
    assert state.history[-1].trigger_event == "SAFE_MODE_RECOVERING_1_OF_3"

    state = handler.process_fsm_state(state)
    assert state.context_data["ship_state_name"] == ShipState.SAFE_MODE.value
    assert state.context_data["safe_mode_exit_hits"] == "2"
    assert state.history[-1].trigger_event == "SAFE_MODE_RECOVERING_2_OF_3"

    state = handler.process_fsm_state(state)
    assert state.context_data["ship_state_name"] == ShipState.SHIP_IDLE.value
    assert state.history[-1].trigger_event == "SAFE_MODE_EXIT_CONFIRMED"
    assert state.history[-1].status == FSMTransitionStatus.SUCCESS


def test_safe_mode_flapping_resets_exit_counter(monkeypatch) -> None:
    monkeypatch.setenv("QIKI_SAFE_EXIT_CONFIRMATION_COUNT", "3")
    ship_core = _StubShipCore()
    actuator = _StubActuatorController()
    handler = ShipFSMHandler(ship_core, actuator)
    state = _snapshot_with_ship_state(ShipState.SAFE_MODE.value)
    state.context_data["safe_mode_reason"] = "SENSORS_UNAVAILABLE"
    state.context_data["safe_bios_ok"] = "1"
    state.context_data["safe_sensors_ok"] = "1"
    state.context_data["safe_provider_ok"] = "1"

    state = handler.process_fsm_state(state)
    assert state.context_data["safe_mode_exit_hits"] == "1"

    state.context_data["safe_provider_ok"] = "0"
    state = handler.process_fsm_state(state)
    assert state.context_data["ship_state_name"] == ShipState.SAFE_MODE.value
    assert state.context_data["safe_mode_exit_hits"] == "0"
    assert state.history[-1].trigger_event == "SAFE_MODE_HOLD_PROVIDER_UNAVAILABLE"

    state.context_data["safe_provider_ok"] = "1"
    state = handler.process_fsm_state(state)
    assert state.context_data["ship_state_name"] == ShipState.SAFE_MODE.value
    assert state.context_data["safe_mode_exit_hits"] == "1"
    assert state.history[-1].trigger_event == "SAFE_MODE_RECOVERING_1_OF_3"

