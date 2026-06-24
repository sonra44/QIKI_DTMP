"""RUNTIME_SLICE_0008 — Module Attach Validation Pipeline v1 (integration / orchestrator).

Cycle 1 RED matrix test. Consolidates Slices 0001-0007 into one deterministic attach
validation pipeline: one entrypoint, ordered validation, a single AttachDecision
contract (with stage + audit_event_id + evidence_card_id), audit for EVERY outcome,
read-only Evidence Card for every outcome, no body_config mutation on rejection, and
stable reason precedence.

Fails to import until ``run_attach_pipeline`` / ``AttachDecision`` exist (intended red).
"""

from __future__ import annotations

import pytest

from qiki.services.q_core_agent.core.body_structure import (
    AttachDecision,
    BodyConfigSnapshot,
    EventStoreRegistrationSink,
    ModuleAttachRequest,
    ModulePassport,
    register_module,
    run_attach_pipeline,
    MODULE_PASSPORT_MISSING,
    MODULE_PASSPORT_INVALID,
    MOUNT_POINT_UNKNOWN,
    MOUNT_POINT_OCCUPIED,
    MODULE_MOUNT_CLASS_FORBIDDEN,
)
from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.operator_console.orion_v.evidence_card import (
    evidence_card_from_audit_event,
)

_MID = "test_sensor_module_001"


def _occupied_body() -> BodyConfigSnapshot:
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")
    p = ModulePassport("existing_module", "sensor", "F06")
    r = ModuleAttachRequest("req-0", "existing_module", "F06", passport=p)
    _, body = register_module(body, r, audit_sink=EventStoreRegistrationSink(store))
    return body


def _case_missing():
    body = BodyConfigSnapshot.skeleton()
    req = ModuleAttachRequest("req", _MID, "F06", passport=None)
    return body, req, "rejected", MODULE_PASSPORT_MISSING, "passport_presence", False


def _case_invalid():
    body = BodyConfigSnapshot.skeleton()
    req = ModuleAttachRequest("req", _MID, "F06", passport=ModulePassport("other_id", "sensor", "F06"))
    return body, req, "rejected", MODULE_PASSPORT_INVALID, "passport_integrity", False


def _case_unknown():
    body = BodyConfigSnapshot.skeleton()
    req = ModuleAttachRequest("req", _MID, "F99", passport=ModulePassport(_MID, "sensor", "F99"))
    return body, req, "rejected", MOUNT_POINT_UNKNOWN, "mount_existence", False


def _case_occupied():
    body = _occupied_body()
    req = ModuleAttachRequest("req", _MID, "F06", passport=ModulePassport(_MID, "sensor", "F06"))
    return body, req, "rejected", MOUNT_POINT_OCCUPIED, "mount_occupancy", False


def _case_forbidden():
    body = BodyConfigSnapshot.skeleton()
    req = ModuleAttachRequest("req", _MID, "F06", passport=ModulePassport(_MID, "reactor-class", "F06"))
    return body, req, "rejected", MODULE_MOUNT_CLASS_FORBIDDEN, "mount_compatibility", False


def _case_valid():
    body = BodyConfigSnapshot.skeleton()
    req = ModuleAttachRequest("req", _MID, "F06", passport=ModulePassport(_MID, "sensor", "F06"))
    return body, req, "attached", None, "registration", True


_CASES = {
    "missing": _case_missing,
    "invalid": _case_invalid,
    "unknown": _case_unknown,
    "occupied": _case_occupied,
    "forbidden": _case_forbidden,
    "valid": _case_valid,
}


@pytest.mark.parametrize("case_name", list(_CASES))
def test_attach_validation_pipeline_returns_expected_decision_for_each_case(case_name: str) -> None:
    body, request, exp_status, exp_reason, exp_stage, exp_bcu = _CASES[case_name]()
    store = EventStore(backend="memory")

    decision, _updated = run_attach_pipeline(body, request, store=store)

    assert isinstance(decision, AttachDecision)
    assert decision.status == exp_status
    assert decision.reason_code == exp_reason
    assert decision.stage == exp_stage
    assert decision.body_config_updated is exp_bcu
    assert decision.runtime_ready is False
    assert decision.capability_status in {"inactive", "not_evaluated"}

    # every outcome is audit-backed and surfaces an evidence card.
    assert decision.audit_event_id
    audit_event = next(e for e in store.recent(20) if e.event_id == decision.audit_event_id)
    card = evidence_card_from_audit_event(audit_event)
    assert card.read_only is True
    assert decision.evidence_card_id == card.card_id


def test_attach_validation_pipeline_does_not_mutate_body_config_on_any_rejection() -> None:
    for case_name in ("missing", "invalid", "unknown", "occupied", "forbidden"):
        body, request, *_ = _CASES[case_name]()
        before_occ = dict(body.face_occupancy)
        before_mods = tuple(body.modules)
        store = EventStore(backend="memory")

        decision, updated = run_attach_pipeline(body, request, store=store)

        assert decision.status == "rejected"
        # body structure unchanged (audit store may grow, but the body cannot).
        assert dict(updated.face_occupancy) == before_occ
        assert tuple(updated.modules) == before_mods


def test_valid_attach_mutates_only_module_registry_and_mount_occupancy() -> None:
    body, request, *_ = _case_valid()
    store = EventStore(backend="memory")

    decision, updated = run_attach_pipeline(body, request, store=store)

    assert decision.status == "attached"
    assert decision.body_config_updated is True
    # allowed mutations only.
    assert updated.face_occupancy["F06"] == _MID
    assert any(m["module_id"] == _MID for m in updated.modules)
    # forbidden side effects.
    assert decision.runtime_ready is False
    assert decision.capability_status in {"inactive", "not_evaluated"}
    # no new faces created; unrelated faces untouched.
    assert set(updated.face_occupancy.keys()) == set(body.face_occupancy.keys())
    assert updated.face_occupancy["F07"] == "free"


@pytest.mark.parametrize(
    "build, expected_reason",
    [
        # missing passport + unknown mount -> MISSING wins
        (
            lambda: ModuleAttachRequest("r", _MID, "F99", passport=None),
            MODULE_PASSPORT_MISSING,
        ),
        # invalid passport + occupied mount -> INVALID wins
        (
            lambda: ModuleAttachRequest("r", _MID, "F06", passport=ModulePassport("x", "sensor", "F06")),
            MODULE_PASSPORT_INVALID,
        ),
        # unknown mount + forbidden class -> UNKNOWN wins
        (
            lambda: ModuleAttachRequest("r", _MID, "F99", passport=ModulePassport(_MID, "reactor-class", "F99")),
            MOUNT_POINT_UNKNOWN,
        ),
    ],
)
def test_attach_validation_reason_precedence_is_stable(build, expected_reason) -> None:
    body = _occupied_body()  # F06 occupied (relevant to the occupied/invalid combo)
    store = EventStore(backend="memory")
    decision, _ = run_attach_pipeline(body, build(), store=store)
    assert decision.reason_code == expected_reason


def test_attach_pipeline_evidence_card_matches_audit_source() -> None:
    body, request, *_ = _case_forbidden()
    store = EventStore(backend="memory")
    decision, _ = run_attach_pipeline(body, request, store=store)

    audit_event = next(e for e in store.recent(20) if e.event_id == decision.audit_event_id)
    card = evidence_card_from_audit_event(audit_event)
    assert card.source_type == "audit"
    assert card.reason_code == decision.reason_code
    assert card.subject_id == audit_event.payload.get("module_id")
    assert card.operation == "module_attach"
    assert card.read_only is True


@pytest.mark.parametrize(
    "case_name, context_fields",
    [
        ("occupied", ("requested_module_id", "existing_module_id")),
        ("invalid", ("requested_module_id", "validation_error", "passport_module_id")),
        ("unknown", ("requested_module_id", "known_mount")),
    ],
)
def test_attach_decision_preserves_registration_rejection_context(
    case_name: str,
    context_fields: tuple[str, ...],
) -> None:
    body, request, *_ = _CASES[case_name]()
    direct_store = EventStore(backend="memory")
    direct_result, _ = register_module(
        body,
        request,
        audit_sink=EventStoreRegistrationSink(direct_store),
    )

    pipeline_store = EventStore(backend="memory")
    decision, _ = run_attach_pipeline(body, request, store=pipeline_store)

    assert decision.reason_code == direct_result.reason_code
    assert decision.audit_event_id
    for field in context_fields:
        assert getattr(decision, field) == getattr(direct_result, field)
