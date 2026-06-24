"""Phase 4 #8 — EvidenceCard must expose IF-ORION-EVIDENCE-001 / canon §17 fields.

Canon QIKI Body v0.2.2 §19.4 (06_INTERFACE_CONTROL.md) IF-ORION-EVIDENCE-001
requires: claim_id, claim_text, source_type, freshness, trust_status,
related_module_id, reason_codes, audit_link, blackbox_relevance, operator_action.

These fields must be derived CONSERVATIVELY from the audit event/payload, with no
invention (no "fresh", no blackbox/action unless the audit payload asserts it).
This RED test pins the conservative contract before the fields exist.
"""

from __future__ import annotations

from qiki.services.q_core_agent.core.body_structure import (
    MODULE_PASSPORT_MISSING,
    SOURCE_OWNER,
)
from qiki.services.q_core_agent.core.event_store import SystemEvent, TruthState
from qiki.services.operator_console.orion_v.evidence_card import (
    evidence_card_from_audit_event,
)


def _audit_event(**payload_extra) -> SystemEvent:
    payload = {
        "module_id": "mod-x",
        "attempted_mount": "F06",
        "reason_code": MODULE_PASSPORT_MISSING,
        "source_owner": SOURCE_OWNER,
    }
    payload.update(payload_extra)
    return SystemEvent(
        event_id="audit-evt-9",
        ts=42.0,
        subsystem=SOURCE_OWNER,
        event_type="module_attach_rejected",
        payload=payload,
        tick_id=None,
        truth_state=TruthState.OK,
        reason=MODULE_PASSPORT_MISSING,
    )


def test_claim_id_equals_card_id() -> None:
    card = evidence_card_from_audit_event(_audit_event())
    assert card.claim_id == card.card_id


def test_claim_text_equals_operator_summary() -> None:
    card = evidence_card_from_audit_event(_audit_event())
    assert card.claim_text == card.operator_summary


def test_freshness_is_unknown_not_invented() -> None:
    card = evidence_card_from_audit_event(_audit_event())
    assert card.freshness == "unknown"


def test_related_module_id_from_audit() -> None:
    card = evidence_card_from_audit_event(_audit_event())
    assert card.related_module_id == "mod-x"


def test_reason_codes_contains_reason() -> None:
    card = evidence_card_from_audit_event(_audit_event())
    assert MODULE_PASSPORT_MISSING in card.reason_codes


def test_audit_link_is_event_id_for_audit_source() -> None:
    card = evidence_card_from_audit_event(_audit_event())
    assert card.audit_link == card.source_id == "audit-evt-9"


def test_blackbox_relevance_defaults_false() -> None:
    card = evidence_card_from_audit_event(_audit_event())
    assert card.blackbox_relevance is False


def test_blackbox_relevance_true_only_when_payload_asserts() -> None:
    card = evidence_card_from_audit_event(_audit_event(blackbox_relevance=True))
    assert card.blackbox_relevance is True


def test_operator_action_not_invented() -> None:
    card = evidence_card_from_audit_event(_audit_event())
    assert card.operator_action is None
