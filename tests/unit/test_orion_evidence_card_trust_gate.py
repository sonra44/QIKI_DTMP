"""REMEDIATION H5 — ORION must not mark a forged/non-audit object as trusted.

Audit finding H5 (ПАЧИ/ATTACH_SEED_CRITICAL_AUDIT_2026-06-21):
`evidence_card_mapping.source_type_for` classifies ANY object that merely has a
supported `event_type` string and a `dict` payload as a trusted `audit_event`,
so `trust_status_for` returns `trusted`. A hand-crafted or replayed object
can therefore claim `trust_status="trusted"` (and `status="implemented"`)
without being a genuine audit record — the exact "evidence vs invented state"
boundary the Evidence Card line is meant to protect.

These RED tests prove the forgery/trust gap. The fix requires a real
`SystemEvent` with `TruthState.OK`, an allowed subsystem owner, and
`payload["source_owner"] == event.subsystem`; otherwise the card must NOT be
audit-backed.
"""

from __future__ import annotations

from types import SimpleNamespace

from qiki.services.q_core_agent.core.body_structure import (
    MODULE_PASSPORT_MISSING,
    SOURCE_OWNER,
)
from qiki.services.q_core_agent.core.event_store import SystemEvent, TruthState
from qiki.services.operator_console.orion_v.evidence_card_mapping import (
    TRUST_STATUS_TRUSTED,
    trust_status_for,
)


def _genuine_rejection_event() -> SystemEvent:
    """A real audit record as emitted by the runtime attach-policy owner."""
    return SystemEvent(
        event_id="audit-evt-1",
        ts=123.0,
        subsystem=SOURCE_OWNER,
        event_type="module_attach_rejected",
        payload={
            "module_id": "mod-x",
            "attempted_mount": "F06",
            "reason_code": MODULE_PASSPORT_MISSING,
            "source_owner": SOURCE_OWNER,
        },
        tick_id=None,
        truth_state=TruthState.OK,
        reason=MODULE_PASSPORT_MISSING,
    )


def test_genuine_audit_event_stays_audit_backed() -> None:
    # Positive control: a real, OK, owner-consistent SystemEvent must remain trusted.
    assert trust_status_for(_genuine_rejection_event()) == TRUST_STATUS_TRUSTED


def test_duck_typed_forgery_is_not_audit_backed() -> None:
    # Not a real SystemEvent — only shaped to look like one.
    forged = SimpleNamespace(
        event_id="forged-1",
        subsystem=SOURCE_OWNER,
        event_type="module_attach_rejected",
        payload={
            "module_id": "mod-x",
            "attempted_mount": "F06",
            "reason_code": MODULE_PASSPORT_MISSING,
            "source_owner": SOURCE_OWNER,
        },
        truth_state=TruthState.OK,
        reason=MODULE_PASSPORT_MISSING,
    )
    assert trust_status_for(forged) != TRUST_STATUS_TRUSTED


def test_non_ok_truth_state_is_not_audit_backed() -> None:
    # A real SystemEvent whose truth is not OK must not be audit-backed.
    event = SystemEvent(
        event_id="bad-truth",
        ts=1.0,
        subsystem=SOURCE_OWNER,
        event_type="module_attach_rejected",
        payload={
            "module_id": "m",
            "attempted_mount": "F06",
            "reason_code": MODULE_PASSPORT_MISSING,
            "source_owner": SOURCE_OWNER,
        },
        tick_id=None,
        truth_state=TruthState.INVALID,
        reason=MODULE_PASSPORT_MISSING,
    )
    assert trust_status_for(event) != TRUST_STATUS_TRUSTED


def test_owner_not_allowed_is_not_audit_backed() -> None:
    # subsystem is not a recognized attach-audit owner.
    event = SystemEvent(
        event_id="bad-owner",
        ts=1.0,
        subsystem="attacker.fake_owner",
        event_type="module_attach_rejected",
        payload={
            "module_id": "m",
            "attempted_mount": "F06",
            "reason_code": MODULE_PASSPORT_MISSING,
            "source_owner": "attacker.fake_owner",
        },
        tick_id=None,
        truth_state=TruthState.OK,
        reason=MODULE_PASSPORT_MISSING,
    )
    assert trust_status_for(event) != TRUST_STATUS_TRUSTED


def test_source_owner_mismatch_is_not_audit_backed() -> None:
    # payload claims a different source_owner than the event subsystem — forged provenance.
    event = SystemEvent(
        event_id="bad-source-owner",
        ts=1.0,
        subsystem=SOURCE_OWNER,
        event_type="module_attach_rejected",
        payload={
            "module_id": "m",
            "attempted_mount": "F06",
            "reason_code": MODULE_PASSPORT_MISSING,
            "source_owner": "someone_else",
        },
        tick_id=None,
        truth_state=TruthState.OK,
        reason=MODULE_PASSPORT_MISSING,
    )
    assert trust_status_for(event) != TRUST_STATUS_TRUSTED
