"""IF-CMD-BUS-001 target-only lifecycle projection for module attach.

This slice does not implement a real command bus, publish path, ACK loop, or
effect confirmation. It only exposes a conservative command-lifecycle record
from the existing attach/audit result so ORION can show missing lifecycle stages
without treating ACK as effect confirmation.
"""

from __future__ import annotations

from dataclasses import fields

from qiki.services.q_core_agent.core.body_structure import (
    AttachDecision,
    BodyConfigSnapshot,
    CommandLifecycleRecord,
    ModuleAttachRequest,
    ModulePassport,
    command_lifecycle_from_attach_decision,
    run_attach_pipeline,
    MODULE_MOUNT_CLASS_FORBIDDEN,
)
from qiki.services.q_core_agent.core.event_store import EventStore


_IF_CMD_BUS_FIELDS = {
    "command_id",
    "command_type",
    "source",
    "target_subsystem",
    "requested_mode",
    "requested_intensity",
    "duration_s",
    "priority",
    "expected_effect",
    "risk_class",
    "validation_state",
    "publish_state",
    "ACK_state",
    "effect_state",
    "audit_state",
    "reason_codes",
}


def test_command_lifecycle_record_exposes_if_cmd_bus_fields() -> None:
    record_fields = {field.name for field in fields(CommandLifecycleRecord)}

    assert _IF_CMD_BUS_FIELDS <= record_fields


def test_attach_success_maps_to_command_lifecycle_without_publish_ack_or_effect_claims() -> None:
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")
    request = ModuleAttachRequest(
        request_id="cmd-attach-1",
        module_id="test_sensor_module_001",
        mount_point="F06",
        passport=ModulePassport("test_sensor_module_001", "sensor", "F06"),
    )
    decision, _ = run_attach_pipeline(body, request, store=store)

    record = command_lifecycle_from_attach_decision(request, decision)

    assert record.command_id == "cmd-attach-1"
    assert record.command_type == "module_attach"
    assert record.target_subsystem == "module"
    assert record.requested_mode == "attach"
    assert record.validation_state == "allowed"
    assert record.audit_state == "written"
    assert record.publish_state == "missing"
    assert record.ACK_state == "missing"
    assert record.effect_state == "missing"
    assert record.reason_codes == ()


def test_attach_rejection_maps_validation_rejected_without_fake_ack_or_effect() -> None:
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")
    request = ModuleAttachRequest(
        request_id="cmd-attach-2",
        module_id="test_forbidden_module_001",
        mount_point="F06",
        passport=ModulePassport("test_forbidden_module_001", "reactor-class", "F06"),
    )
    decision, _ = run_attach_pipeline(body, request, store=store)

    record = command_lifecycle_from_attach_decision(request, decision)

    assert record.validation_state == "rejected"
    assert record.audit_state == "written"
    assert record.publish_state == "missing"
    assert record.ACK_state == "missing"
    assert record.effect_state == "missing"
    assert record.reason_codes == ("CMD_REJECTED", MODULE_MOUNT_CLASS_FORBIDDEN)


def test_command_lifecycle_marks_audit_unavailable_when_audit_id_is_missing() -> None:
    decision = AttachDecision(
        status="rejected",
        stage="validation",
        reason_code=MODULE_MOUNT_CLASS_FORBIDDEN,
        module_id="test_forbidden_module_001",
        mount_point="F06",
        body_config_updated=False,
        runtime_ready=False,
        passport_status="validated",
        capability_status="not_evaluated",
        audit_event_id="",
        evidence_card_id="",
    )
    request = ModuleAttachRequest(
        request_id="cmd-attach-3",
        module_id="test_forbidden_module_001",
        mount_point="F06",
        passport=ModulePassport("test_forbidden_module_001", "reactor-class", "F06"),
    )

    record = command_lifecycle_from_attach_decision(request, decision)

    assert record.audit_state == "missing"
    assert record.reason_codes == (
        "CMD_REJECTED",
        MODULE_MOUNT_CLASS_FORBIDDEN,
        "AUDIT_UNAVAILABLE",
    )
