from typing import List, TYPE_CHECKING
from .interfaces import INeuralEngine
from .agent_logger import logger

if TYPE_CHECKING:
    from .agent import AgentContext
    from qiki.shared.config_models import QCoreAgentConfig
from qiki.shared.models.core import Proposal, ProposalTypeEnum
from uuid import UUID as PyUUID


class NeuralEngine(INeuralEngine):
    """
    Neural Engine responsible for generating proposals based on ML models.
    For MVP, this will be a simple placeholder.
    """

    def __init__(self, context: "AgentContext", config: "QCoreAgentConfig"):
        self.context = context
        self.config = config
        self.mock_neural_proposals_enabled = config.mock_neural_proposals_enabled
        logger.info(
            f"NeuralEngine initialized. Mock proposals enabled: {self.mock_neural_proposals_enabled}"
        )

    def generate_proposals(self, context: "AgentContext") -> List[Proposal]:
        logger.debug("Generating proposals from Neural Engine (placeholder).")
        proposals: List[Proposal] = []

        if self.mock_neural_proposals_enabled:
            mock_proposal = Proposal(
                proposal_id=PyUUID("00000000-0000-0000-0000-000000000002"),
                source_module_id="neural_engine_mock",
                proposed_actions=[],  # No actions for mock
                justification="Mock proposal from Neural Engine.",
                priority=0.5,
                confidence=0.7,
                type=ProposalTypeEnum.PLANNING,
            )
            proposals.append(mock_proposal)
            logger.debug("Generated mock proposal from Neural Engine.")

        return proposals
