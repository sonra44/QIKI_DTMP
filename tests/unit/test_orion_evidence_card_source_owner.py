"""MEDIUM #9 — ORION evidence card must surface the audit source_owner (provenance).

Canon ADR-0014 (06_INTERFACE_CONTROL / ADR-0014-orion-evidence-station):
"ORION must show source ... audit trail"; REQ-ORION-001/002 require ORION to show
sources / provenance. The audit payload carries source_owner — the subsystem owner
that recorded the rejection (attach_policy vs passport_validator), and the H5
invariant is payload["source_owner"] == event.subsystem. That provenance was dropped
at the card boundary (_FACT_KEYS) so the operator could not see which owner rejected.

This pins source_owner reaching the card facts, including the per-reason owner
distinction (passport_validator for invalid passport, attach_policy otherwise).
"""

from __future__ import annotations

from qiki.services.q_core_agent.core.body_structure import (
    MODULE_PASSPORT_INVALID,
    MODULE_PASSPORT_MISSING,
    PASSPORT_VALIDATOR_OWNER,
    SOURCE_OWNER,
)
from qiki.services.q_core_agent.core.event_store import SystemEvent, TruthState
from qiki.services.operator_console.orion_v.evidence_card import (
    evidence_card_from_audit_event,
)


def _event(subsystem: str, reason: str, **payload_extra) -> SystemEvent:
    payload = {
        "module_id": "mod-x",
        "attempted_mount": "F06",
        "reason_code": reason,
        "source_owner": subsystem,
    }
    payload.update(payload_extra)
    return SystemEvent(
        event_id="evt-9",
        ts=1.0,
        subsystem=subsystem,
        event_type="module_attach_rejected",
        payload=payload,
        tick_id=None,
        truth_state=TruthState.OK,
        reason=reason,
    )


def test_card_surfaces_source_owner_from_audit() -> None:
    card = evidence_card_from_audit_event(_event(SOURCE_OWNER, MODULE_PASSPORT_MISSING))
    assert card.facts.get("source_owner") == SOURCE_OWNER


def test_card_source_owner_matches_event_subsystem_invariant() -> None:
    # H5 provenance invariant (payload.source_owner == event.subsystem), surfaced to operator.
    ev = _event(SOURCE_OWNER, MODULE_PASSPORT_MISSING)
    card = evidence_card_from_audit_event(ev)
    assert card.facts.get("source_owner") == ev.subsystem


def test_card_surfaces_passport_validator_owner_for_invalid_passport() -> None:
    card = evidence_card_from_audit_event(
        _event(PASSPORT_VALIDATOR_OWNER, MODULE_PASSPORT_INVALID, validation_error="module_id_mismatch")
    )
    assert card.facts.get("source_owner") == PASSPORT_VALIDATOR_OWNER
