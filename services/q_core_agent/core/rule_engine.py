from typing import List, TYPE_CHECKING
from .interfaces import IRuleEngine
from .agent_logger import logger

if TYPE_CHECKING:
    from .agent import AgentContext
from generated.proposal_pb2 import Proposal
from generated.actuator_raw_out_pb2 import (
    ActuatorCommand as ActuatorCommandPb2,
)  # Alias to avoid conflict
from generated.common_types_pb2 import UUID, Unit
from generated.fsm_state_pb2 import FSMStateEnum  # Import FSMStateEnum
from google.protobuf.timestamp_pb2 import Timestamp


class RuleEngine(IRuleEngine):
    """
    Rule Engine responsible for generating proposals based on predefined rules.
    For MVP, this will include basic safety rules.
    """

    def __init__(self, context: "AgentContext", config: dict):
        self.context = context
        self.config = config
        logger.info("RuleEngine initialized.")

    def generate_proposals(self, context: "AgentContext") -> List[Proposal]:
        logger.debug("Generating proposals from Rule Engine.")
        proposals: List[Proposal] = []

        # Example Rule: If BIOS is not OK, propose to go to SAFE_MODE
        if not context.is_bios_ok():
            logger.warning("Rule triggered: BIOS not OK. Proposing SAFE_MODE.")
            timestamp = Timestamp()
            timestamp.GetCurrentTime()

            # Create a dummy actuator command for SAFE_MODE
            safe_mode_command = ActuatorCommandPb2(
                actuator_id=UUID(value="system_controller"),
                timestamp=timestamp,
                command_type=ActuatorCommandPb2.CommandType.SET_MODE,
                int_value=FSMStateEnum.ERROR_STATE,  # Assuming ERROR_STATE maps to safe mode
                unit=Unit.UNIT_UNSPECIFIED,
            )

            proposal = Proposal(
                proposal_id=UUID(value="rule_engine_safe_mode"),
                source_module_id="rule_engine",
                timestamp=timestamp,
                proposed_actions=[safe_mode_command],
                justification="BIOS reported critical errors. Entering safe mode.",
                priority=0.99,  # High priority
                confidence=1.0,  # High confidence
                type=Proposal.ProposalType.SAFETY,
            )
            proposals.append(proposal)

        # Add more rules here based on sensor data, FSM state, etc.

        return proposals
