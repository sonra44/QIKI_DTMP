from typing import TYPE_CHECKING, Optional
from .interfaces import IFSMHandler
from .agent_logger import logger

if TYPE_CHECKING:
    from .agent import AgentContext
    from ..state.store import AsyncStateStore

# StateStore imports
from ..state.types import (
    FsmSnapshotDTO,
    FsmState,
    TransitionStatus,
    create_transition,
    next_snapshot,
)
from generated.fsm_state_pb2 import FSMStateEnum as ProtoFSMStateEnum # Renamed for clarity
from shared.converters.protobuf_pydantic import proto_fsm_state_snapshot_to_pydantic_fsm_snapshot_dto, pydantic_fsm_snapshot_dto_to_proto_fsm_state_snapshot

class FSMHandler(IFSMHandler):
    def __init__(self, context: "AgentContext"): # Removed state_store for now
        self.context = context
        # self.state_store = state_store # Removed state_store for now
        logger.info("FSMHandler initialized.")

    # Removed duplicate import here, it's already at the top of the file

    async def process_fsm_dto(self, proto_fsm_state: "ProtoFsmStateSnapshot") -> "ProtoFsmStateSnapshot":
        # Convert Protobuf snapshot to Pydantic DTO
        current_fsm_state_dto = proto_fsm_state_snapshot_to_pydantic_fsm_snapshot_dto(proto_fsm_state)

        logger.debug(f"FSMHandler: Processing FSM state: {current_fsm_state_dto.state.name}") # Use .name for FsmState

        next_state = current_fsm_state_dto.state # Default to no change (FsmState enum)
        trigger_event = "NO_CHANGE" # Default trigger event

        # Example FSM logic (using FsmState enum)
        # If current state is BOOTING and BIOS is OK, transition to IDLE
        if current_fsm_state_dto.state == FsmState.BOOTING and self.context.is_bios_ok():
            next_state = FsmState.IDLE
            trigger_event = "BOOT_COMPLETE"
        # If current state is BOOTING and BIOS is NOT OK, transition to ERROR_STATE
        elif current_fsm_state_dto.state == FsmState.BOOTING and not self.context.is_bios_ok():
            next_state = FsmState.ERROR_STATE
            trigger_event = "BIOS_ERROR"
        # If current state is IDLE and there are proposals, transition to ACTIVE
        elif current_fsm_state_dto.state == FsmState.IDLE and self.context.has_valid_proposals():
            next_state = FsmState.ACTIVE
            trigger_event = "PROPOSALS_RECEIVED"
        # If current state is ACTIVE and there are no proposals, transition to IDLE
        elif current_fsm_state_dto.state == FsmState.ACTIVE and not self.context.has_valid_proposals():
            next_state = FsmState.IDLE
            trigger_event = "NO_PROPOSALS"
        # If current state is ERROR_STATE and BIOS is OK, transition to IDLE (recovery)
        elif current_fsm_state_dto.state == FsmState.ERROR_STATE and self.context.is_bios_ok():
            next_state = FsmState.IDLE
            trigger_event = "ERROR_CLEARED"

        # Create a transition DTO
        transition_dto = create_transition(
            from_state=current_fsm_state_dto.state,
            to_state=next_state,
            trigger=trigger_event,
            status=TransitionStatus.SUCCESS # Always success for now in FSMHandler
        )

        # Create a new snapshot with the next state, including the transition
        new_snapshot_dto = next_snapshot(current_fsm_state_dto, next_state, trigger_event, transition_dto)

        logger.debug(f"FSM transitioned from {current_fsm_state_dto.state.name} to {new_snapshot_dto.state.name}") # Use .name for FsmState
        
        # Convert Pydantic DTO back to Protobuf snapshot
        return pydantic_fsm_snapshot_dto_to_proto_fsm_state_snapshot(new_snapshot_dto)

    # Additional methods for FSM management (e.g., handling events, loading rules)
    # ...