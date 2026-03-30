import pytest

from qiki.services.q_core_agent.core.agent import AgentContext
from qiki.services.q_core_agent.core.neural_engine import (
    NeuralEngine,
    _strip_actions_for_proposals_only,
)
from qiki.services.q_core_agent.core.openai_responses_client import OpenAIResponsesClient
from qiki.shared.config_models import QCoreAgentConfig


def _make_engine() -> NeuralEngine:
    config = QCoreAgentConfig(
        tick_interval=1,
        log_level="INFO",
        recovery_delay=1,
        proposal_confidence_threshold=0.8,
        mock_neural_proposals_enabled=False,
        grpc_server_address="localhost:50051",
    )
    return NeuralEngine(context=AgentContext(), config=config)


def test_strip_actions_for_proposals_only_removes_known_fields() -> None:
    payload = {
        "proposals": [
            {
                "title": "T",
                "justification": "J",
                "priority": 0.5,
                "confidence": 0.5,
                "type": "PLANNING",
                "actions": [{"op": "do"}],
                "proposed_actions": [{"op": "do2"}],
            }
        ]
    }
    stripped = _strip_actions_for_proposals_only(payload)
    assert "actions" not in stripped["proposals"][0]
    assert "proposed_actions" not in stripped["proposals"][0]


def test_neuralengine_proposals_always_have_no_actions_when_no_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    engine = _make_engine()

    proposals = engine.generate_proposals(AgentContext())

    assert proposals, "expected fallback proposal when OPENAI_API_KEY is missing"
    assert all(len(p.proposed_actions) == 0 for p in proposals)


@pytest.mark.parametrize("bad_value", ["", " ", "\n"])
def test_neuralengine_missing_key_variants_always_fallback(monkeypatch, bad_value: str) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", bad_value)
    engine = _make_engine()
    proposals = engine.generate_proposals(AgentContext())
    assert proposals
    assert all(len(p.proposed_actions) == 0 for p in proposals)


def test_neuralengine_strips_actions_from_llm_payload(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def _fake_create_response_json_schema(self, *, system_prompt, user_json, json_schema):  # noqa: ARG001
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                '{"proposals":[{"title":"T","justification":"J","priority":0.5,'
                                '"confidence":0.5,"type":"PLANNING","actions":[{"op":"x"}],'
                                '"proposed_actions":[{"op":"y"}]}]}'
                            ),
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(
        OpenAIResponsesClient,
        "create_response_json_schema",
        _fake_create_response_json_schema,
        raising=True,
    )

    engine = _make_engine()
    proposals = engine.generate_proposals(AgentContext())

    assert proposals
    assert all(len(p.proposed_actions) == 0 for p in proposals)
