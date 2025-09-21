from typing import Dict, List, TYPE_CHECKING, Tuple
from .interfaces import IRuleEngine
from .agent_logger import logger
from .guard_table import GuardEvaluationResult

if TYPE_CHECKING:
    from .agent import AgentContext
from qiki.shared.models.core import (
    Proposal,
    ActuatorCommand,
    UnitEnum,
    CommandTypeEnum,
    ProposalTypeEnum,
)
from generated.fsm_state_pb2 import FSMStateEnum
from uuid import UUID as PyUUID, uuid4  # For Pydantic UUID and proposal IDs


class RuleEngine(IRuleEngine):
    """
    Rule Engine responsible for generating proposals based on predefined rules.
    For MVP, this will include basic safety rules.
    """

    _GUARD_EVENT_HANDLERS: Dict[str, str] = {
        "RADAR_ALERT_UNKNOWN_CLOSE": "_build_safe_mode_proposal",
        "RADAR_ALERT_TRANSPONDER_SPOOF": "_build_safe_mode_proposal",
        "RADAR_ALERT_TRANSPONDER_OFF": "_build_safe_mode_proposal",
        "RADAR_ALERT_HOSTILE_APPROACH": "_build_safe_mode_proposal",
        "RADAR_ALERT_FOE_APPROACH": "_build_safe_mode_proposal",
        "RADAR_WARNING_UNKNOWN_PROXIMITY": "_build_warning_proposal",
        "RADAR_ALERT_SPOOF": "_build_warning_proposal",
    }

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
            proposals.append(self._build_safe_mode_proposal())

        proposals.extend(self._generate_guard_proposals(context))

        # Add more rules here based on sensor data, FSM state, etc.

        return proposals

    def _generate_guard_proposals(self, context: "AgentContext") -> List[Proposal]:
        guard_events = getattr(context, "guard_events", []) or []
        if not guard_events:
            return []

        proposals: List[Proposal] = []
        seen: set[Tuple[str, str]] = set()

        for event in guard_events:
            if not isinstance(event, GuardEvaluationResult):
                continue

            key = (event.rule_id, event.track_id)
            if key in seen:
                continue
            seen.add(key)

            handler_name = self._GUARD_EVENT_HANDLERS.get(event.fsm_event)
            if handler_name is None:
                if event.severity == "critical":
                    proposals.append(self._build_safe_mode_proposal(event))
                continue

            handler = getattr(self, handler_name, None)
            if handler is None:
                logger.debug("Guard handler %s not implemented", handler_name)
                continue

            proposal = handler(event)
            if proposal is not None:
                proposals.append(proposal)

        return proposals

    def _build_safe_mode_proposal(
        self, guard_event: GuardEvaluationResult | None = None
    ) -> Proposal:
        justification = "BIOS reported critical errors. Entering safe mode."
        if guard_event is not None:
            justification = (
                f"Guard {guard_event.rule_id} triggered ({guard_event.severity}). "
                "Transitioning to SAFE_MODE."
            )

        safe_mode_command = ActuatorCommand(
            actuator_id=PyUUID("00000000-0000-0000-0000-000000000001"),
            command_type=CommandTypeEnum.SET_MODE,
            int_value=FSMStateEnum.ERROR_STATE,
            unit=UnitEnum.UNIT_UNSPECIFIED,
        )

        return Proposal(
            proposal_id=uuid4(),
            source_module_id="rule_engine",
            proposed_actions=[safe_mode_command],
            justification=justification,
            priority=0.99,
            confidence=1.0,
            type=ProposalTypeEnum.SAFETY,
        )

    def _build_warning_proposal(
        self, guard_event: GuardEvaluationResult | None = None
    ) -> Proposal | None:
        if guard_event is None:
            return None

        return Proposal(
            proposal_id=uuid4(),
            source_module_id="rule_engine",
            proposed_actions=[],
            justification=(
                f"Guard {guard_event.rule_id} warning for track {guard_event.track_id}."
            ),
            priority=0.5,
            confidence=0.6,
            type=ProposalTypeEnum.DIAGNOSTICS,
        )
