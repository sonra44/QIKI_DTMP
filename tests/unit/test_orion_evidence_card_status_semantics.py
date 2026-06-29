"""ORION Evidence Card status semantics hardening.

``card.status == "implemented"`` is evidence-card conformance, not module
runtime readiness and not full QIKI Body runtime compliance.
"""

from __future__ import annotations

from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    ModuleAttachRequest,
    ModulePassport,
    run_attach_pipeline,
)
from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.operator_console.orion_v.evidence_card import evidence_card_from_audit_event
from qiki.services.operator_console.orion_v.evidence_card_mapping import (
    EVIDENCE_STATUS_IMPLEMENTED,
    SOURCE_TYPE_AUDIT,
)


def test_evidence_status_implemented_does_not_mean_module_runtime_ready() -> None:
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")
    request = ModuleAttachRequest(
        request_id="req-status-semantics",
        module_id="test_sensor_module_001",
        mount_point="F06",
        passport=ModulePassport("test_sensor_module_001", "sensor", "F06"),
    )

    decision, _updated = run_attach_pipeline(body, request, store=store)
    audit_event = next(e for e in store.recent(20) if e.event_id == decision.audit_event_id)
    card = evidence_card_from_audit_event(audit_event)

    assert card.source_type == SOURCE_TYPE_AUDIT
    assert card.status == EVIDENCE_STATUS_IMPLEMENTED
    assert card.subject_status == "attached"
    assert card.runtime_ready is False
    assert decision.runtime_ready is False
    assert decision.capability_status in {"inactive", "not_evaluated"}
    assert card.facts["runtime_ready"] is False
    assert card.facts["capability_status"] in {"inactive", "not_evaluated"}
