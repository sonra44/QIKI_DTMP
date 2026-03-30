import json

from fsm_state_pb2 import FSMStateEnum, FsmStateSnapshot

from qiki.services.q_core_agent.core.event_store import EventStore, TruthState
from qiki.services.q_core_agent.core.ship_actuators import PropulsionMode, ShipActuatorController
from qiki.services.q_core_agent.core.ship_fsm_handler import ShipFSMHandler, ShipState


def test_event_store_append_and_recent_order() -> None:
    store = EventStore(maxlen=10, enabled=True)
    store.append_new(subsystem="FSM", event_type="E1", payload={"i": 1}, truth_state=TruthState.OK, reason="ok")
    store.append_new(subsystem="FSM", event_type="E2", payload={"i": 2}, truth_state=TruthState.OK, reason="ok")

    recent = store.recent(2)

    assert [event.event_type for event in recent] == ["E1", "E2"]


def test_event_store_ring_buffer_evicts_oldest() -> None:
    store = EventStore(maxlen=2, enabled=True)
    store.append_new(subsystem="FSM", event_type="A", payload={}, truth_state=TruthState.OK, reason="")
    store.append_new(subsystem="FSM", event_type="B", payload={}, truth_state=TruthState.OK, reason="")
    store.append_new(subsystem="FSM", event_type="C", payload={}, truth_state=TruthState.OK, reason="")

    recent = store.recent(10)

    assert [event.event_type for event in recent] == ["B", "C"]


def test_event_store_export_jsonl(tmp_path) -> None:
    store = EventStore(maxlen=10, enabled=True)
    store.append_new(
        subsystem="ACTUATORS",
        event_type="ACTUATION_RECEIPT",
        payload={"status": "accepted"},
        truth_state=TruthState.OK,
        reason="COMMAND_ACCEPTED_NO_EXECUTION_ACK",
    )

    output_path = tmp_path / "events.jsonl"
    written = store.export_jsonl(str(output_path))

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    row = json.loads(lines[0])
    assert written == 1
    assert len(lines) == 1
    assert row["subsystem"] == "ACTUATORS"
    assert row["event_type"] == "ACTUATION_RECEIPT"


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


class _StubShipCoreForFSM:
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
        return "stub-event-store-ship"


class _StubActuatorForFSM:
    def __init__(self, mode: PropulsionMode = PropulsionMode.IDLE) -> None:
        self.current_mode = mode

    def emergency_stop(self) -> bool:
        return True


def _snapshot(ship_state_name: str) -> FsmStateSnapshot:
    state = FsmStateSnapshot()
    state.current_state = FSMStateEnum.ACTIVE
    state.context_data["ship_state_name"] = ship_state_name
    return state


def test_fsm_transition_event_is_recorded() -> None:
    store = EventStore(maxlen=50, enabled=True)
    handler = ShipFSMHandler(_StubShipCoreForFSM(), _StubActuatorForFSM(), event_store=store)
    state = _snapshot(ShipState.SHIP_STARTUP.value)

    handler.process_fsm_state(state)

    events = store.filter(subsystem="FSM", event_type="FSM_TRANSITION")
    assert events
    assert events[-1].payload["from_state"] == ShipState.SHIP_STARTUP.value
    assert events[-1].payload["to_state"] == ShipState.SHIP_IDLE.value


def test_safe_mode_enter_event_is_recorded() -> None:
    store = EventStore(maxlen=50, enabled=True)
    handler = ShipFSMHandler(_StubShipCoreForFSM(), _StubActuatorForFSM(), event_store=store)
    state = _snapshot(ShipState.FLIGHT_CRUISE.value)
    state.context_data["safe_bios_ok"] = "0"

    handler.process_fsm_state(state)

    events = store.filter(subsystem="SAFE_MODE", event_type="SAFE_MODE")
    assert events
    assert events[-1].payload["action"] == "enter"
    assert events[-1].payload["reason"] == "BIOS_UNAVAILABLE"


class _ShipCoreActuatorOK:
    def send_actuator_command(self, _command) -> None:
        return None

    _config = {}


def test_actuation_receipt_event_is_recorded() -> None:
    store = EventStore(maxlen=50, enabled=True)
    controller = ShipActuatorController(_ShipCoreActuatorOK(), event_store=store)

    result = controller.set_main_drive_thrust_result(25.0)

    events = store.filter(subsystem="ACTUATORS", event_type="ACTUATION_RECEIPT")
    assert result.status.value == "accepted"
    assert events
    assert events[-1].payload["action"] == "set_main_drive_thrust"
    assert events[-1].payload["status"] == "accepted"


def test_sensor_trust_verdict_event_is_recorded() -> None:
    store = EventStore(maxlen=50, enabled=True)
    handler = ShipFSMHandler(_StubShipCoreForFSM(), _StubActuatorForFSM(), event_store=store)

    trusted = handler.ship_context.get_trusted_station_track()

    events = store.filter(subsystem="SENSORS", event_type="SENSOR_TRUST_VERDICT")
    assert trusted.ok is False
    assert trusted.reason.value == "NO_DATA"
    assert events
    assert events[-1].payload["sensor_kind"] == "station_track"
    assert events[-1].payload["reason"] == "NO_DATA"
