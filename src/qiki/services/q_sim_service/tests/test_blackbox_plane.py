from __future__ import annotations

from dataclasses import fields

from qiki.services.q_sim_service.core.world_model import (
    BlackboxRecord,
    blackbox_record_from_runtime_event,
)


def test_if_blackbox_record_exposes_canon_fields_and_recorded_state() -> None:
    record_fields = {field.name for field in fields(BlackboxRecord)}

    assert {
        "record_id",
        "timestamp",
        "trigger_event",
        "severity",
        "body_state_snapshot",
        "power_snapshot",
        "thermal_snapshot",
        "motion_snapshot",
        "sensor_snapshot",
        "command_chain",
        "audit_refs",
        "reason_codes",
        "loss_context",
        "recovery_notes",
    } <= record_fields
    assert "recorded_state" in record_fields


def test_if_blackbox_mapper_defaults_target_only_not_recorded() -> None:
    record = blackbox_record_from_runtime_event(None, state=None)

    assert record.recorded_state == "not_recorded"
    assert record.trigger_event == "missing"
    assert record.severity == "missing"
    assert record.body_state_snapshot == {}
    assert record.reason_codes == (
        "BLACKBOX_TARGET_ONLY",
        "BLACKBOX_NOT_RECORDED",
        "BLACKBOX_TRIGGER_MISSING",
    )


def test_if_blackbox_mapper_detects_critical_power_loss_from_snapshot() -> None:
    record = blackbox_record_from_runtime_event(
        {"event_id": "evt-power", "timestamp": 42.0},
        state={
            "power": {"soc_pct": 0.0, "supercap_soc_pct": 0.0, "faults": ["BUS_V_ZERO"]},
            "thermal": {"nodes": []},
        },
    )

    assert record.record_id == "bb:evt-power"
    assert record.timestamp == 42.0
    assert record.trigger_event == "critical power loss"
    assert record.severity == "critical"
    assert record.recorded_state == "not_recorded"
    assert record.power_snapshot["soc_pct"] == 0.0
    assert "BLACKBOX_TRIGGER_DETECTED" in record.reason_codes
    assert "BLACKBOX_NOT_RECORDED" in record.reason_codes


def test_if_blackbox_mapper_detects_critical_thermal_event() -> None:
    record = blackbox_record_from_runtime_event(
        {"event_id": "evt-thermal"},
        state={"thermal": {"nodes": [{"id": "core", "temp_c": 95.0, "warn_c": 70.0, "tripped": True}]}},
    )

    assert record.trigger_event == "critical thermal event"
    assert record.severity == "critical"
    assert record.thermal_snapshot["nodes"][0]["id"] == "core"


def test_if_blackbox_mapper_surfaces_nbl_emergency_packet_relevance() -> None:
    record = blackbox_record_from_runtime_event(
        {"event_id": "evt-nbl", "event_type": "nbl_packet", "blackbox_relevance": True},
        state={"power": {"nbl_active": True}, "thermal": {"nodes": []}},
        audit_refs=("audit-1",),
    )

    assert record.trigger_event == "NBL emergency packet"
    assert record.audit_refs == ("audit-1",)
    assert record.recorded_state == "not_recorded"
    assert "BLACKBOX_NOT_RECORDED" in record.reason_codes
