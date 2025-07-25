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
        self.confidence_threshold = config.get("proposal_confidence_threshold", 0.6)
        logger.info(f"ProposalEvaluator initialized with confidence_threshold: {self.confidence_threshold}")

    def evaluate_proposals(self, proposals: List[Proposal]) -> List[Proposal]:
        logger.debug(f"Evaluating {len(proposals)} proposals.")
        accepted_proposals: List[Proposal] = []

        if not proposals:
            logger.debug("No proposals to evaluate.")
            return []

        # Sort proposals by priority (higher value first) and then by confidence
        # Assuming ProposalType enum values map to increasing priority (e.g., SAFETY > PLANNING)
        sorted_proposals = sorted(proposals, key=lambda p: (p.type, p.priority), reverse=True)

        best_proposal: Proposal = None

        for proposal in sorted_proposals:
            # Basic validation: check confidence
            if proposal.confidence < self.confidence_threshold: # Configurable threshold
                logger.debug(f"Rejected proposal {proposal.proposal_id.value} (Confidence too low: {proposal.confidence})")
                continue

            # For MVP, select the highest priority/confidence proposal
            if best_proposal is None or \
               (proposal.type > best_proposal.type) or \
               (proposal.type == best_proposal.type and proposal.priority > best_proposal.priority) or \
               (proposal.type == best_proposal.type and proposal.priority == best_proposal.priority and proposal.confidence > best_proposal.confidence):
                best_proposal = proposal

        if best_proposal:
            accepted_proposals.append(best_proposal)
            logger.info(f"Accepted proposal: {best_proposal.proposal_id.value} (Source: {best_proposal.source_module_id}, Type: {best_proposal.type.name}, Priority: {best_proposal.priority}, Confidence: {best_proposal.confidence})")
        else:
            logger.info("No proposals met the acceptance criteria.")

        return accepted_proposals