from typing import List
from .interfaces import IProposalEvaluator
from .agent_logger import logger
from generated.proposal_pb2 import Proposal


class ProposalEvaluator(IProposalEvaluator):
    """
    Evaluates proposals from the Q-Mind and selects the most suitable ones.
    This version considers priority and confidence.
    """

    def __init__(self, config: dict):
        self.config = config
        self.confidence_threshold = config.proposal_confidence_threshold
        logger.info(
            f"ProposalEvaluator initialized with confidence_threshold: {self.confidence_threshold}"
        )

    def evaluate_proposals(self, proposals: List[Proposal]) -> List[Proposal]:
        logger.debug(f"Evaluating {len(proposals)} proposals.")
        accepted_proposals: List[Proposal] = []

        if not proposals:
            logger.debug("No proposals to evaluate.")
            return []

        # Sort proposals by type priority (SAFETY=1 > PLANNING=2, lower values first) and then by priority (higher values first)
        # ProposalType: SAFETY=1 has higher logical priority than PLANNING=2, so sort by type ascending, priority descending
        sorted_proposals = sorted(proposals, key=lambda p: (p.type, -p.priority))

        best_proposal: Proposal = None

        for proposal in sorted_proposals:
            # Basic validation: check confidence
            if (
                proposal.confidence < self.confidence_threshold
            ):  # Configurable threshold
                logger.debug(
                    f"Rejected proposal {proposal.proposal_id.value} (Confidence too low: {proposal.confidence})"
                )
                continue

            # For MVP, select the highest priority/confidence proposal
            # Note: For ProposalType, lower enum values have higher priority (SAFETY=1 > PLANNING=2)
            if (
                best_proposal is None
                or (proposal.type < best_proposal.type)
                or (
                    proposal.type == best_proposal.type
                    and proposal.priority > best_proposal.priority
                )
                or (
                    proposal.type == best_proposal.type
                    and proposal.priority == best_proposal.priority
                    and proposal.confidence > best_proposal.confidence
                )
            ):
                best_proposal = proposal

        if best_proposal:
            accepted_proposals.append(best_proposal)
            logger.info(
                f"Accepted proposal: {best_proposal.proposal_id.value} (Source: {best_proposal.source_module_id}, Type: {best_proposal.type}, Priority: {best_proposal.priority}, Confidence: {best_proposal.confidence})"
            )
        else:
            logger.info("No proposals met the acceptance criteria.")

        return accepted_proposals
