from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from qiki.shared.models.orion_qiki_protocol import (
    EnvironmentMode,
    EnvironmentSetV1,
    EnvironmentSnapshotV1,
    IntentV1,
    LangHint,
    ProposalV1,
    ProposalsBatchV1,
    SelectionV1,
)


def test_intent_v1_roundtrip() -> None:
    payload = IntentV1(
        text="scan 360",
        lang_hint=LangHint.EN,
        screen="Events/События",
        selection=SelectionV1(kind="incident", id="INC|sensor|core"),
        ts=1700000000000,
        environment_mode=EnvironmentMode.FACTORY,
        snapshot_min={"nats": True, "unread": 3},
    )
    dumped = payload.model_dump()
    reloaded = IntentV1.model_validate(dumped)
    assert reloaded.version == 1
    assert reloaded.text == "scan 360"
    assert reloaded.selection.kind == "incident"
    assert reloaded.snapshot_min["unread"] == 3


def test_intent_v1_requires_fields() -> None:
    with pytest.raises(ValidationError):
        IntentV1.model_validate({"version": 1, "text": "x"})


def test_proposal_v1_actions_must_be_empty_in_stage_a() -> None:
    ok = ProposalV1(
        proposal_id="P1",
        title="Title",
        justification="Justification",
        priority=50,
        confidence=0.6,
        proposed_actions=[],
    )
    assert ok.proposed_actions == []

    with pytest.raises(ValidationError):
        ProposalV1(
            proposal_id="P2",
            title="Title",
            justification="Justification",
            priority=50,
            confidence=0.6,
            proposed_actions=[{"op": "do"}],
        )


def test_batch_v1_json_roundtrip() -> None:
    batch = ProposalsBatchV1(
        ts=1700000000000,
        proposals=[
            ProposalV1(
                proposal_id="P1",
                title="T",
                justification="J",
                priority=10,
                confidence=0.9,
            )
        ],
        metadata={"request_id": "RID"},
    )
    raw = batch.model_dump_json()
    parsed = ProposalsBatchV1.model_validate_json(raw)
    assert parsed.version == 1
    assert parsed.proposals[0].proposal_id == "P1"
    assert parsed.metadata["request_id"] == "RID"


def test_version_compatibility_strict() -> None:
    payload = {
        "version": 2,
        "ts": 1700000000000,
        "proposals": [],
        "metadata": {},
    }
    with pytest.raises(ValidationError):
        ProposalsBatchV1.model_validate(payload)

    # Ensure we can still deserialize strict v1 payloads even if they came as JSON.
    raw = json.dumps({"version": 1, "ts": 1700000000000, "proposals": [], "metadata": {}}, ensure_ascii=False)
    parsed = ProposalsBatchV1.model_validate_json(raw)
    assert parsed.version == 1


def test_strict_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        IntentV1.model_validate(
            {
                "version": 1,
                "text": "x",
                "lang_hint": "auto",
                "screen": "System/Система",
                "selection": {"kind": "none"},
                "ts": 1700000000000,
                "environment_mode": "FACTORY",
                "snapshot_min": {},
                "extra": "nope",
            }
        )


def test_environment_snapshot_v1_roundtrip() -> None:
    snap = EnvironmentSnapshotV1(
        ts=1700000000000,
        environment_mode=EnvironmentMode.MISSION,
        source="q_core_agent",
    )
    raw = snap.model_dump_json()
    parsed = EnvironmentSnapshotV1.model_validate_json(raw)
    assert parsed.version == 1
    assert parsed.environment_mode == EnvironmentMode.MISSION


def test_environment_set_v1_requires_mode() -> None:
    payload = {"version": 1, "ts": 1700000000000, "environment_mode": "FACTORY"}
    parsed = EnvironmentSetV1.model_validate(payload)
    assert parsed.environment_mode == EnvironmentMode.FACTORY

    with pytest.raises(ValidationError):
        EnvironmentSetV1.model_validate({"version": 1, "ts": 1})
