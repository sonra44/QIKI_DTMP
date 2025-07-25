from typing import Dict, Any
from .interfaces import IFSMHandler
from .agent_logger import logger
from .agent import AgentContext # Import AgentContext
from generated.fsm_state_pb2 import FSMState, StateTransition
from google.protobuf.timestamp_pb2 import Timestamp

class FSMHandler(IFSMHandler):
    """
    Handles the Finite State Machine (FSM) logic for the Q-Core Agent.
    This handler is responsible for processing the current FSM state,
    evaluating conditions, and determining the next state.
    """
    def __init__(self, context: AgentContext):
        self.context = context
        logger.info("FSMHandler initialized.")

    def process_fsm_state(self, current_fsm_state: FSMState) -> FSMState:
        logger.debug(f"Processing FSM state: {current_fsm_state.current_state_name}")

        next_state = FSMState()
        next_state.CopyFrom(current_fsm_state) # Start with a copy of the current state

        # State transition logic
        current_state_name = current_fsm_state.current_state_name
        bios_ok = self.context.is_bios_ok()
        has_proposals = self.context.has_valid_proposals()

        new_state_name = current_state_name
        trigger_event = ""
        new_phase = current_fsm_state.phase

        if current_state_name == "BOOTING":
            if bios_ok:
                new_state_name = "IDLE"
                trigger_event = "BOOT_COMPLETE"
                new_phase = FSMState.FSMPhase.IDLE
            else:
                new_state_name = "ERROR_STATE"
                trigger_event = "BIOS_ERROR"
                new_phase = FSMState.FSMPhase.ERROR_STATE
        elif current_state_name == "IDLE":
            if not bios_ok:
                new_state_name = "ERROR_STATE"
                trigger_event = "BIOS_ERROR"
                new_phase = FSMState.FSMPhase.ERROR_STATE
            elif has_proposals:
                new_state_name = "ACTIVE"
                trigger_event = "PROPOSALS_RECEIVED"
                new_phase = FSMState.FSMPhase.ACTIVE
        elif current_state_name == "ACTIVE":
            if not bios_ok:
                new_state_name = "ERROR_STATE"
                trigger_event = "BIOS_ERROR"
                new_phase = FSMState.FSMPhase.ERROR_STATE
            elif not has_proposals:
                new_state_name = "IDLE"
                trigger_event = "NO_PROPOSALS"
                new_phase = FSMState.FSMPhase.IDLE
        elif current_state_name == "ERROR_STATE":
            if bios_ok and not has_proposals: # Simple recovery: if BIOS is OK and no active proposals, go to IDLE
                new_state_name = "IDLE"
                trigger_event = "ERROR_CLEARED"
                new_phase = FSMState.FSMPhase.IDLE

        if new_state_name != current_state_name:
            logger.info(f"FSM Transition: {current_state_name} -> {new_state_name} (Trigger: {trigger_event})")
            new_transition = StateTransition(
                from_state=current_state_name,
                to_state=new_state_name,
                trigger_event=trigger_event
            )
            new_transition.timestamp.GetCurrentTime()
            next_state.current_state_name = new_state_name
            next_state.history.append(new_transition)
            next_state.phase = new_phase

        # Update timestamp for the new state snapshot
        next_state.timestamp.GetCurrentTime()

        logger.debug(f"FSM new state: {next_state.current_state_name}")
        return next_state