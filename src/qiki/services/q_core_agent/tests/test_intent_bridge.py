from __future__ import annotations

import pytest
from pydantic import ValidationError

from qiki.services.q_core_agent.intent_bridge import build_invalid_intent_proposals, build_stub_proposals
from qiki.shared.models.orion_qiki_protocol import EnvironmentMode, IntentV1, LangHint, SelectionV1


def test_build_stub_proposals_actions_empty() -> None:
    intent = IntentV1(
        text="scan 360",
        lang_hint=LangHint.EN,
        screen="Events/События",
        selection=SelectionV1(kind="incident", id="INC|x"),
        ts=1700000000000,
        environment_mode=EnvironmentMode.FACTORY,
        snapshot_min={"incidents_top": [{"incident_id": "i1"}]},
    )
    batch = build_stub_proposals(intent, environment_mode=EnvironmentMode.FACTORY)
    assert batch.version == 1
    assert 1 <= len(batch.proposals) <= 3
    assert batch.metadata["screen"] == "Events/События"
    assert batch.metadata["intent_ts"] == 1700000000000
    for p in batch.proposals:
        assert p.proposed_actions == []


def test_build_stub_proposals_mission_is_less_verbose() -> None:
    intent = IntentV1(
        text="scan 360",
        lang_hint=LangHint.EN,
        screen="Events/События",
        selection=SelectionV1(kind="incident", id="INC|x"),
        ts=1700000000000,
        environment_mode=EnvironmentMode.MISSION,
        snapshot_min={"incidents_top": [{"incident_id": "i1"}]},
    )
    batch = build_stub_proposals(intent, environment_mode=EnvironmentMode.MISSION)
    assert 1 <= len(batch.proposals) <= 2
    assert batch.metadata["verbosity"] == "low"


def test_build_invalid_intent_proposals() -> None:
    batch = build_invalid_intent_proposals(ValueError("bad payload"))
    assert batch.version == 1
    assert len(batch.proposals) == 1
    assert batch.proposals[0].proposal_id == "invalid-intent"
    assert batch.proposals[0].proposed_actions == []


def test_intent_schema_requires_environment_and_screen() -> None:
    with pytest.raises(ValidationError):
        IntentV1.model_validate({"version": 1, "text": "x", "ts": 1})
