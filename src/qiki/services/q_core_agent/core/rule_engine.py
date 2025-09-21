from typing import List, TYPE_CHECKING
from .interfaces import IRuleEngine
from .agent_logger import logger

if TYPE_CHECKING:
    from .agent import AgentContext
from shared.models.core import (
    Proposal,
    ActuatorCommand,
    UnitEnum,
    CommandTypeEnum,
    ProposalTypeEnum,
)
from generated.fsm_state_pb2 import FSMStateEnum
from uuid import UUID as PyUUID  # For Pydantic UUID


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
            # Create a dummy actuator command for SAFE_MODE
            safe_mode_command = ActuatorCommand(
                actuator_id=PyUUID("00000000-0000-0000-0000-000000000001"),
                command_type=CommandTypeEnum.SET_MODE,
                int_value=FSMStateEnum.ERROR_STATE,  # Assuming ERROR_STATE maps to safe mode
                unit=UnitEnum.UNIT_UNSPECIFIED,
            )

            proposal = Proposal(
                proposal_id=uuid4(),  # Using a generated UUID
                source_module_id="rule_engine",
                proposed_actions=[safe_mode_command],
                justification="BIOS reported critical errors. Entering safe mode.",
                priority=0.99,  # High priority
                confidence=1.0,  # High confidence
                type=ProposalTypeEnum.SAFETY,
            )
            proposals.append(proposal)

        # Add more rules here based on sensor data, FSM state, etc.

        return proposals

        return proposals
