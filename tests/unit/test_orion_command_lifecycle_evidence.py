"""Stage 1 / IF-CMD-BUS-001 — ORION operator surface of the command lifecycle.

Canon §18.7: ORION must distinguish allowed / published / ACK accepted / effect
confirmed / failed / partial / timeout. ADR-0015: ACK is NOT effect confirmation —
ORION must never present ACK, or a missing effect, as confirmed.

Stage 1 is a conservative target-only projection: validation + audit are known from
the attach path; publish / ACK / effect have no real producer yet and MUST stay
missing/target-only (Canon != Implemented). This pins the honest ORION surface.
"""

from __future__ import annotations

import dataclasses

from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    ModuleAttachRequest,
    ModulePassport,
    command_lifecycle_from_attach_decision,
    run_attach_pipeline,
)
from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.operator_console.orion_v.body_structure_evidence import (
    command_lifecycle_to_evidence,
)


def _record(passport):
    store = EventStore(backend="memory")
    req = ModuleAttachRequest("req-1", "mod-x", "F06", passport=passport)
    decision, _ = run_attach_pipeline(BodyConfigSnapshot.skeleton(), req, store=store)
    return command_lifecycle_from_attach_decision(req, decision)


def test_lifecycle_evidence_surfaces_validation_allowed() -> None:
    ev = command_lifecycle_to_evidence(_record(ModulePassport("mod-x", "sensor", "F06")))
    assert ev.validation_label == "allowed"


def test_lifecycle_evidence_surfaces_rejection_with_reason() -> None:
    ev = command_lifecycle_to_evidence(_record(None))
    assert ev.validation_label == "rejected"
    assert "MODULE_PASSPORT_MISSING" in ev.reason_codes


def test_lifecycle_evidence_publish_ack_effect_stay_missing() -> None:
    # No real command-bus / ACK / effect producer -> must not be presented as positive.
    ev = command_lifecycle_to_evidence(_record(ModulePassport("mod-x", "sensor", "F06")))
    assert ev.published_label in ("missing", "target-only")
    assert ev.ack_label in ("missing", "target-only")
    assert ev.effect_label in ("missing", "target-only")


def test_lifecycle_evidence_never_claims_effect_confirmed() -> None:
    # Hard ADR-0015 guard: a missing effect must never be surfaced as confirmed.
    ev = command_lifecycle_to_evidence(_record(ModulePassport("mod-x", "sensor", "F06")))
    assert ev.effect_label != "confirmed"
    assert ev.ack_label != "effect confirmed"


def test_lifecycle_evidence_audit_known() -> None:
    ev = command_lifecycle_to_evidence(_record(None))
    assert ev.audit_label == "written"
    assert ev.read_only is True


def test_operator_text_does_not_deny_observed_ack() -> None:
    # CODEX_BLOCKER fix: if ACK is observed but effect missing, operator_text must NOT
    # deny the observed ACK, and must still not claim the effect confirmed (ADR-0015).
    base = _record(ModulePassport("mod-x", "sensor", "F06"))
    acked = dataclasses.replace(base, ACK_state="accepted")
    ev = command_lifecycle_to_evidence(acked)
    assert ev.ack_label == "ACK accepted"
    assert ev.effect_label != "confirmed"
    assert "not yet observed: ACK" not in ev.operator_text
    assert "ACK accepted" in ev.operator_text
