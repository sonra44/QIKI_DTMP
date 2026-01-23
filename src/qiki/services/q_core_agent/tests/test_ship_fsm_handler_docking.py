from unittest.mock import Mock

from qiki.services.q_core_agent.core.ship_fsm_handler import (
    FSMState,
    ShipFSMHandler,
    ShipState,
)


def test_docking_approach_transitions_to_engaged_when_docked():
    ship_core = Mock()
    actuator_controller = Mock()

    handler = ShipFSMHandler(ship_core, actuator_controller)

    handler.ship_context.is_ship_systems_ok = Mock(return_value=True)
    handler.ship_context.has_navigation_capability = Mock(return_value=True)
    handler.ship_context.is_docking_target_in_range = Mock(return_value=True)
    handler.ship_context.get_current_propulsion_mode = Mock()
    handler.ship_context.get_current_propulsion_mode.return_value = Mock(value="MANEUVERING")
    handler.ship_context.is_docking_engaged = Mock(return_value=True)

    current = FSMState()
    current.current_state_name = ShipState.DOCKING_APPROACH.value
    current.phase = FSMState.FSMPhase.DOCKING

    next_state = handler.process_fsm_state(current)

    assert next_state.current_state_name == ShipState.DOCKING_ENGAGED.value
    assert next_state.phase == FSMState.FSMPhase.DOCKING
    assert len(next_state.history) == 1
    assert next_state.history[0].from_state == ShipState.DOCKING_APPROACH.value
    assert next_state.history[0].to_state == ShipState.DOCKING_ENGAGED.value
    assert next_state.history[0].trigger_event == "DOCKING_COMPLETE"


def test_docking_approach_returns_to_maneuvering_when_target_lost():
    ship_core = Mock()
    actuator_controller = Mock()

    handler = ShipFSMHandler(ship_core, actuator_controller)

    handler.ship_context.is_ship_systems_ok = Mock(return_value=True)
    handler.ship_context.has_navigation_capability = Mock(return_value=True)
    handler.ship_context.is_docking_target_in_range = Mock(return_value=False)
    handler.ship_context.is_docking_engaged = Mock(return_value=False)
    handler.ship_context.get_current_propulsion_mode = Mock()
    handler.ship_context.get_current_propulsion_mode.return_value = Mock(value="MANEUVERING")

    current = FSMState()
    current.current_state_name = ShipState.DOCKING_APPROACH.value
    current.phase = FSMState.FSMPhase.DOCKING

    next_state = handler.process_fsm_state(current)

    assert next_state.current_state_name == ShipState.FLIGHT_MANEUVERING.value
    assert next_state.phase == FSMState.FSMPhase.FLIGHT
    assert len(next_state.history) == 1
    assert next_state.history[0].trigger_event == "DOCKING_TARGET_LOST"
