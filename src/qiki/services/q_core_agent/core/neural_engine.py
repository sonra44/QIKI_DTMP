import os
from typing import Any, Dict, List, Literal, TYPE_CHECKING
from .interfaces import INeuralEngine
from .agent_logger import logger

if TYPE_CHECKING:
    from .agent import AgentContext
    from qiki.shared.config_models import QCoreAgentConfig
from qiki.shared.models.core import Proposal, ProposalTypeEnum
from uuid import UUID as PyUUID
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .openai_responses_client import (
    OpenAIResponsesClient,
    OpenAIResponsesError,
    parse_response_json,
)

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message


class _LLMProposalV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    justification: str = Field(min_length=1, max_length=800)
    priority: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    type: Literal["SAFETY", "PLANNING", "DIAGNOSTICS", "EXPLORATION"]


class _LLMProposalsResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposals: List[_LLMProposalV1] = Field(min_length=1, max_length=3)


def _strip_actions_for_proposals_only(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove any "actions" or "proposed_actions" keys from each proposal in the payload.
    
    If the payload contains a "proposals" list of dictionaries, this function removes those keys from each dictionary in-place and returns the (possibly modified) payload.
    
    Returns:
        payload (Dict[str, Any]): The original payload with "actions" and "proposed_actions" removed from proposal items when present.
    """
    proposals = payload.get("proposals")
    if isinstance(proposals, list):
        for item in proposals:
            if isinstance(item, dict):
                item.pop("actions", None)
                item.pop("proposed_actions", None)
    return payload


class NeuralEngine(INeuralEngine):
    """
    Neural Engine responsible for generating proposals based on ML models.
    For MVP, this will be a simple placeholder.
    """

    def __init__(self, context: "AgentContext", config: "QCoreAgentConfig"):
        """
        Initialize the NeuralEngine instance and load OpenAI-related configuration from environment variables.
        
        Parameters:
            context (AgentContext): Runtime agent context used by the engine.
            config (QCoreAgentConfig): Agent configuration providing flags such as mock_neural_proposals_enabled.
        
        Details:
            - Saves provided context and config on the instance.
            - Reads and stores OpenAI settings from environment variables:
                OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL, OPENAI_TIMEOUT_S,
                OPENAI_MAX_OUTPUT_TOKENS, OPENAI_MAX_RETRIES, OPENAI_TEMPERATURE.
            - Sets the mock proposals enabled flag from config and logs initialization.
        """
        self.context = context
        self.config = config
        self.mock_neural_proposals_enabled = config.mock_neural_proposals_enabled

        self._openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self._openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        self._openai_base_url = os.getenv(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        ).strip()
        self._openai_timeout_s = float(os.getenv("OPENAI_TIMEOUT_S", "20"))
        self._openai_max_output_tokens = int(
            os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "500")
        )
        self._openai_max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
        self._openai_temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))

        logger.info(
            f"NeuralEngine initialized. Mock proposals enabled: {self.mock_neural_proposals_enabled}"
        )

    def generate_proposals(self, context: "AgentContext") -> List[Proposal]:
        """
        Generate a list of Proposal objects using either a mock implementation, a diagnostics fallback, or proposals produced by the OpenAI-backed LLM.
        
        When mock proposals are enabled, returns a single predefined mock Proposal. If no OpenAI API key is configured, returns a single diagnostics Proposal indicating LLM unavailability. If an OpenAI call fails, returns a single diagnostics Proposal containing a truncated (first 200 characters) error message and zeroed priority/confidence. On success, converts each LLM proposal into a Proposal where the justification is formed as "title: justification", priority and confidence are taken from the LLM output, and the proposal type is mapped to ProposalTypeEnum (defaults to PLANNING if unknown).
        
        Returns:
            List[Proposal]: A list containing either mock, diagnostics, or translated LLM proposals.
        """
        logger.debug("Generating proposals from Neural Engine.")
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

        if not self._openai_api_key:
            proposals.append(
                Proposal(
                    proposal_id=PyUUID("00000000-0000-0000-0000-0000000000e5"),
                    source_module_id="neural_engine_openai",
                    proposed_actions=[],
                    justification="LLM unavailable: OPENAI_API_KEY not set.",
                    priority=0.0,
                    confidence=0.0,
                    type=ProposalTypeEnum.DIAGNOSTICS,
                )
            )
            return proposals

        try:
            response_model = self._generate_openai_proposals(context)
        except OpenAIResponsesError as exc:
            logger.warning("OpenAI unavailable for NeuralEngine: %s", exc)
            proposals.append(
                Proposal(
                    proposal_id=uuid4(),
                    source_module_id="neural_engine_openai",
                    proposed_actions=[],
                    justification=f"LLM unavailable: {str(exc)[:200]}",
                    priority=0.0,
                    confidence=0.0,
                    type=ProposalTypeEnum.DIAGNOSTICS,
                )
            )
            return proposals

        for llm_proposal in response_model.proposals:
            proposals.append(
                Proposal(
                    proposal_id=uuid4(),
                    source_module_id="neural_engine_openai",
                    proposed_actions=[],
                    justification=f"{llm_proposal.title}: {llm_proposal.justification}",
                    priority=llm_proposal.priority,
                    confidence=llm_proposal.confidence,
                    type=getattr(
                        ProposalTypeEnum, llm_proposal.type, ProposalTypeEnum.PLANNING
                    ),
                )
            )

        return proposals

    def _generate_openai_proposals(
        self, context: "AgentContext"
    ) -> _LLMProposalsResponseV1:
        """
        Request 1–3 structured proposals from the configured OpenAI Responses API using a minimal agent context and return them validated and sanitized.
        
        Parameters:
            context (AgentContext): Agent state used to build the minimal user context supplied to the LLM.
        
        Returns:
            _LLMProposalsResponseV1: A validated and sanitized response containing 1–3 proposals, each with `title`, `justification`, `priority`, `confidence`, and `type`.
        """
        client = OpenAIResponsesClient(
            api_key=self._openai_api_key,
            model=self._openai_model,
            base_url=self._openai_base_url,
            timeout_s=self._openai_timeout_s,
            max_output_tokens=self._openai_max_output_tokens,
            max_retries=self._openai_max_retries,
            temperature=self._openai_temperature,
        )

        system_prompt = (
            "You are NeuralEngine for QIKI DTMP. Generate 1-3 proposals for the operator.\n"
            "Rules:\n"
            "- Output must be valid JSON that matches the provided JSON Schema.\n"
            "- Do NOT propose executable actions yet; proposals are informational only.\n"
            "- Keep text concise and operational.\n"
            "- priority/confidence are floats in [0,1].\n"
            "- type is one of: SAFETY, PLANNING, DIAGNOSTICS, EXPLORATION.\n"
        )

        user_json: Dict[str, Any] = self._build_min_context(context)
        json_schema = _LLMProposalsResponseV1.model_json_schema()

        raw = client.create_response_json_schema(
            system_prompt=system_prompt,
            user_json=user_json,
            json_schema=json_schema,
        )
        parsed = parse_response_json(response=raw)
        parsed = _strip_actions_for_proposals_only(parsed)
        return _LLMProposalsResponseV1.model_validate(parsed)

    def _build_min_context(self, context: "AgentContext") -> Dict[str, Any]:
        """
        Build a minimal serializable context dictionary extracted from the agent runtime context for use in LLM prompts.
        
        The returned dictionary contains the following keys:
        - bios_status: a serializable representation of context.bios_status or None.
        - fsm_state: a serializable representation of context.fsm_state or None.
        - guard_events: a list of up to the first 20 serializable guard event objects (empty list if none).
        - world_snapshot: a serializable representation of context.world_snapshot or None.
        
        Serialization rules applied to each value:
        - protobuf Message objects are converted to dicts while preserving proto field names.
        - objects with a `model_dump()` method use that output.
        - objects with a `dict()` method use that output.
        - None is preserved; any other value is returned as-is.
        """
        def _dump(value: Any) -> Any:
            if value is None:
                return None
            if isinstance(value, Message):
                return MessageToDict(value, preserving_proto_field_name=True)
            if hasattr(value, "model_dump"):
                return value.model_dump()
            if hasattr(value, "dict"):
                return value.dict()  # type: ignore[no-any-return]
            return value

        return {
            "bios_status": _dump(getattr(context, "bios_status", None)),
            "fsm_state": _dump(getattr(context, "fsm_state", None)),
            "guard_events": [
                _dump(event)
                for event in (getattr(context, "guard_events", None) or [])[:20]
            ],
            "world_snapshot": _dump(getattr(context, "world_snapshot", None)),
        }