"""RUNTIME_SLICE_0002 — ORION Evidence Card surfacing for body-structure rejection.

Cycle 1 RED test. Takes the Slice 0001 audit-backed MODULE_PASSPORT_MISSING
rejection (a recorded event_store.SystemEvent) and surfaces it as a read-only
ORION Evidence Card built ONLY from that audit source.

Until ``orion_v/evidence_card.py`` exists this module fails to import (intended
first red). The card is an ORION *projection* of the audit event, NOT a truth-owner:
it must not mark the module runtime-ready and must not invent facts absent from the
audit payload.
"""

from __future__ import annotations

from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    EventStoreRejectionSink,
    ModuleAttachRequest,
    attach_module,
    MODULE_PASSPORT_MISSING,
)
from qiki.services.q_core_agent.core.event_store import EventStore

# Slice 0002 surface (does not exist yet -> ImportError = first red).
from qiki.services.operator_console.orion_v.evidence_card import (
    CARD_TYPE_BODY_MODULE_ATTACH_REJECTION,
    EvidenceCard,
    evidence_card_from_audit_event,
)


def _recorded_rejection_audit_event():
    """Produce a real audit SystemEvent via the Slice 0001 reject->audit path."""
    store = EventStore(backend="memory")
    body = BodyConfigSnapshot.skeleton()
    request = ModuleAttachRequest(
        request_id="req-1", module_id="mod-x", mount_point="F06", passport=None
    )
    attach_module(body, request, audit_sink=EventStoreRejectionSink(store))
    events = store.recent(1)
    assert len(events) == 1
    return events[0]


def test_module_passport_missing_rejection_becomes_read_only_evidence_card() -> None:
    audit_event = _recorded_rejection_audit_event()
    assert audit_event.event_type == "module_attach_rejected"
    assert audit_event.reason == MODULE_PASSPORT_MISSING

    card = evidence_card_from_audit_event(audit_event)

    assert isinstance(card, EvidenceCard)
    assert card.card_type == CARD_TYPE_BODY_MODULE_ATTACH_REJECTION
    assert card.subject_type == "module"
    assert card.subject_id == "mod-x"
    assert card.operation == "module_attach"

    # domain outcome (operator spec §6: status == rejected)
    assert card.subject_status == "rejected"
    # §17 evidence-conformance: audit-backed runtime evidence exists (not target-only)
    assert card.status == "implemented"

    assert card.reason_code == MODULE_PASSPORT_MISSING
    assert card.source_type == "audit_event"
    assert card.source_id == audit_event.event_id
    assert card.related_audit_event_id == audit_event.event_id
    assert card.trust_status == "audit_backed"
    assert card.read_only is True

    # the card does NOT mark the module runtime-ready
    assert card.runtime_ready is False

    # the card does not invent facts: surfaced facts trace to the audit payload
    assert card.facts.get("module_id") == "mod-x"
    assert card.facts.get("attempted_mount") == "F06"
    assert card.facts.get("reason_code") == MODULE_PASSPORT_MISSING

    # honest operator-facing text, no overclaim
    text = card.operator_summary.lower()
    assert "passport" in text
    for banned in (
        "module installed",
        "module active",
        "runtime conforms",
        "qiki body implemented",
    ):
        assert banned not in text
