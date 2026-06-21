"""RUNTIME_SLICE_0002 — ORION Evidence Card mapping contract.

RED test owned by Codex for Cycle 1. It covers the canon/status mapping layer
only; the EvidenceCard normalizer itself is owned by the parallel Claude test.
"""

from __future__ import annotations

from qiki.services.q_core_agent.core.body_structure import (
    MODULE_MOUNT_CLASS_FORBIDDEN,
    MODULE_PASSPORT_INVALID,
    MODULE_PASSPORT_MISSING,
    MOUNT_POINT_UNKNOWN,
    MOUNT_POINT_OCCUPIED,
    SOURCE_OWNER,
)
from qiki.services.q_core_agent.core.event_store import SystemEvent, TruthState
from qiki.services.operator_console.orion_v.evidence_card_mapping import (
    BODY_MODULE_ATTACH_REJECTION,
    BODY_MODULE_ATTACH_REGISTERED,
    forbidden_wording_violations,
    map_module_attach_rejection_event,
    map_module_attach_registered_event,
)


def _module_attach_rejected_event() -> SystemEvent:
    return SystemEvent(
        event_id="audit-evt-1",
        ts=123.0,
        subsystem=SOURCE_OWNER,
        event_type="module_attach_rejected",
        payload={
            "request_id": "req-1",
            "module_id": "mod-x",
            "attempted_mount": "F06",
            "reason_code": MODULE_PASSPORT_MISSING,
            "source_owner": SOURCE_OWNER,
        },
        tick_id=None,
        truth_state=TruthState.OK,
        reason=MODULE_PASSPORT_MISSING,
    )


def _module_attach_registered_event() -> SystemEvent:
    return SystemEvent(
        event_id="audit-evt-2",
        ts=124.0,
        subsystem=SOURCE_OWNER,
        event_type="module_attach_registered",
        payload={
            "request_id": "req-2",
            "module_id": "mod-ok",
            "mount_point": "F07",
            "passport_status": "validated",
            "capability_status": "inactive",
            "runtime_ready": False,
            "source_owner": SOURCE_OWNER,
        },
        tick_id=None,
        truth_state=TruthState.OK,
        reason="MODULE_ATTACH_REGISTERED",
    )


def _mount_point_occupied_rejection_event() -> SystemEvent:
    return SystemEvent(
        event_id="audit-evt-3",
        ts=125.0,
        subsystem=SOURCE_OWNER,
        event_type="module_attach_rejected",
        payload={
            "request_id": "req-3",
            "module_id": "mod-new",
            "attempted_mount": "F06",
            "reason_code": MOUNT_POINT_OCCUPIED,
            "requested_module_id": "mod-new",
            "existing_module_id": "mod-existing",
            "mount_point": "F06",
            "body_config_updated": False,
            "source_owner": SOURCE_OWNER,
        },
        tick_id=None,
        truth_state=TruthState.OK,
        reason=MOUNT_POINT_OCCUPIED,
    )


def _module_mount_class_forbidden_rejection_event() -> SystemEvent:
    return SystemEvent(
        event_id="audit-evt-4",
        ts=126.0,
        subsystem=SOURCE_OWNER,
        event_type="module_attach_rejected",
        payload={
            "request_id": "req-4",
            "module_id": "mod-reactor",
            "attempted_mount": "F06",
            "reason_code": MODULE_MOUNT_CLASS_FORBIDDEN,
            "module_class": "reactor-class",
            "mount_point": "F06",
            "body_config_updated": False,
            "source_owner": SOURCE_OWNER,
        },
        tick_id=None,
        truth_state=TruthState.OK,
        reason=MODULE_MOUNT_CLASS_FORBIDDEN,
    )


def _module_passport_invalid_rejection_event() -> SystemEvent:
    return SystemEvent(
        event_id="audit-evt-5",
        ts=127.0,
        subsystem=SOURCE_OWNER,
        event_type="module_attach_rejected",
        payload={
            "request_id": "req-5",
            "module_id": "mod-requested",
            "attempted_mount": "F06",
            "reason_code": MODULE_PASSPORT_INVALID,
            "passport_module_id": "mod-passport",
            "validation_error": "module_id_mismatch",
            "body_config_updated": False,
            "source_owner": SOURCE_OWNER,
        },
        tick_id=None,
        truth_state=TruthState.OK,
        reason=MODULE_PASSPORT_INVALID,
    )


def _mount_point_unknown_rejection_event() -> SystemEvent:
    return SystemEvent(
        event_id="audit-evt-6",
        ts=128.0,
        subsystem=SOURCE_OWNER,
        event_type="module_attach_rejected",
        payload={
            "request_id": "req-6",
            "module_id": "mod-unknown-mount",
            "attempted_mount": "F99",
            "reason_code": MOUNT_POINT_UNKNOWN,
            "mount_point": "F99",
            "known_mount": False,
            "body_config_updated": False,
            "source_owner": SOURCE_OWNER,
        },
        tick_id=None,
        truth_state=TruthState.OK,
        reason=MOUNT_POINT_UNKNOWN,
    )


def test_module_attach_rejection_event_maps_to_audit_backed_card_contract() -> None:
    mapped = map_module_attach_rejection_event(_module_attach_rejected_event())

    assert mapped.card_type == BODY_MODULE_ATTACH_REJECTION
    assert mapped.subject_type == "module"
    assert mapped.subject_status == "rejected"
    assert mapped.status == "implemented"
    assert mapped.trust_status == "audit_backed"
    assert mapped.source_type == "audit_event"
    assert mapped.source_id == "audit-evt-1"
    assert mapped.reason_code == MODULE_PASSPORT_MISSING
    assert mapped.module_id == "mod-x"
    assert mapped.attempted_mount == "F06"
    assert mapped.runtime_ready is False
    assert mapped.read_only is True
    assert mapped.operator_summary == "attach rejected: passport missing"


def test_mount_point_occupied_rejection_maps_to_audit_backed_card_contract() -> None:
    mapped = map_module_attach_rejection_event(_mount_point_occupied_rejection_event())

    assert mapped.card_type == BODY_MODULE_ATTACH_REJECTION
    assert mapped.subject_type == "module"
    assert mapped.subject_status == "rejected"
    assert mapped.status == "implemented"
    assert mapped.trust_status == "audit_backed"
    assert mapped.source_type == "audit_event"
    assert mapped.source_id == "audit-evt-3"
    assert mapped.reason_code == MOUNT_POINT_OCCUPIED
    assert mapped.module_id == "mod-new"
    assert mapped.attempted_mount == "F06"
    assert mapped.runtime_ready is False
    assert mapped.read_only is True
    assert mapped.operator_summary == "attach rejected: mount point occupied"
    assert mapped.missing_fields == ()
    assert forbidden_wording_violations(mapped.operator_summary) == ()


def test_module_mount_class_forbidden_rejection_maps_to_audit_backed_card_contract() -> None:
    mapped = map_module_attach_rejection_event(_module_mount_class_forbidden_rejection_event())

    assert mapped.card_type == BODY_MODULE_ATTACH_REJECTION
    assert mapped.subject_type == "module"
    assert mapped.subject_status == "rejected"
    assert mapped.status == "implemented"
    assert mapped.trust_status == "audit_backed"
    assert mapped.source_type == "audit_event"
    assert mapped.source_id == "audit-evt-4"
    assert mapped.reason_code == MODULE_MOUNT_CLASS_FORBIDDEN
    assert mapped.module_id == "mod-reactor"
    assert mapped.attempted_mount == "F06"
    assert mapped.runtime_ready is False
    assert mapped.read_only is True
    assert mapped.operator_summary == "attach rejected: module class forbidden"
    assert mapped.missing_fields == ()
    assert forbidden_wording_violations(mapped.operator_summary) == ()


def test_module_passport_invalid_rejection_maps_to_audit_backed_card_contract() -> None:
    mapped = map_module_attach_rejection_event(_module_passport_invalid_rejection_event())

    assert mapped.card_type == BODY_MODULE_ATTACH_REJECTION
    assert mapped.subject_type == "module"
    assert mapped.subject_status == "rejected"
    assert mapped.status == "implemented"
    assert mapped.trust_status == "audit_backed"
    assert mapped.source_type == "audit_event"
    assert mapped.source_id == "audit-evt-5"
    assert mapped.reason_code == MODULE_PASSPORT_INVALID
    assert mapped.module_id == "mod-requested"
    assert mapped.attempted_mount == "F06"
    assert mapped.runtime_ready is False
    assert mapped.read_only is True
    assert mapped.operator_summary == "attach rejected: passport invalid"
    assert mapped.missing_fields == ()
    assert forbidden_wording_violations(mapped.operator_summary) == ()


def test_mount_point_unknown_rejection_maps_to_audit_backed_card_contract() -> None:
    mapped = map_module_attach_rejection_event(_mount_point_unknown_rejection_event())

    assert mapped.card_type == BODY_MODULE_ATTACH_REJECTION
    assert mapped.subject_type == "module"
    assert mapped.subject_status == "rejected"
    assert mapped.status == "implemented"
    assert mapped.trust_status == "audit_backed"
    assert mapped.source_type == "audit_event"
    assert mapped.source_id == "audit-evt-6"
    assert mapped.reason_code == MOUNT_POINT_UNKNOWN
    assert mapped.module_id == "mod-unknown-mount"
    assert mapped.attempted_mount == "F99"
    assert mapped.runtime_ready is False
    assert mapped.read_only is True
    assert mapped.operator_summary == "attach rejected: mount point unknown"
    assert mapped.missing_fields == ()
    assert forbidden_wording_violations(mapped.operator_summary) == ()


def test_module_attach_rejection_mapping_marks_missing_audit_payload_fields() -> None:
    event = _module_attach_rejected_event()
    event.payload.pop("module_id")

    mapped = map_module_attach_rejection_event(event)

    assert mapped.subject_type == "module"
    assert mapped.subject_status == "rejected"
    assert mapped.status == "missing"
    assert mapped.trust_status == "missing"
    assert "ORION_SOURCE_MISSING" in mapped.missing_fields
    assert "module_id" in mapped.missing_fields
    assert mapped.read_only is True


def test_forbidden_wording_guard_targets_generated_operator_text_only() -> None:
    clean = forbidden_wording_violations("attach rejected: passport missing")
    dirty = forbidden_wording_violations("module installed; bridge allowed; command unlocked")

    assert clean == ()
    assert dirty == ("module installed", "command unlocked", "bridge allowed")


def test_module_attach_registered_event_maps_to_audit_backed_inactive_card_contract() -> None:
    mapped = map_module_attach_registered_event(_module_attach_registered_event())

    assert mapped.card_type == BODY_MODULE_ATTACH_REGISTERED
    assert mapped.subject_type == "module"
    assert mapped.subject_status == "attached"
    assert mapped.status == "implemented"
    assert mapped.trust_status == "audit_backed"
    assert mapped.source_type == "audit_event"
    assert mapped.source_id == "audit-evt-2"
    assert mapped.module_id == "mod-ok"
    assert mapped.attempted_mount == "F07"
    assert mapped.passport_status == "validated"
    assert mapped.capability_status == "inactive"
    assert mapped.runtime_ready is False
    assert mapped.read_only is True
    assert mapped.operator_summary == "module registered: passport validated, capabilities inactive"
    assert forbidden_wording_violations(mapped.operator_summary) == ()
    assert mapped.missing_fields == ()


def test_module_attach_registered_forbidden_wording_guard_blocks_activation_claims() -> None:
    dirty = forbidden_wording_violations(
        "module active; capabilities active; powered; command unlocked; "
        "pdu enabled; thermally cleared"
    )

    assert dirty == (
        "module active",
        "capabilities active",
        "powered",
        "command unlocked",
        "pdu enabled",
        "thermally cleared",
    )


def test_module_attach_registered_mapping_marks_missing_required_payload_fields() -> None:
    event = _module_attach_registered_event()
    event.payload.pop("capability_status")

    mapped = map_module_attach_registered_event(event)

    assert mapped.card_type == BODY_MODULE_ATTACH_REGISTERED
    assert mapped.subject_status == "attached"
    assert mapped.status == "missing"
    assert mapped.trust_status == "missing"
    assert "ORION_SOURCE_MISSING" in mapped.missing_fields
    assert "capability_status" in mapped.missing_fields
    assert "attempted_mount" not in mapped.missing_fields
    assert mapped.read_only is True
