from dataclasses import fields

from qiki.services.q_sim_service.core.world_model import (
    SafeStateRecord,
    safe_state_from_runtime_state,
)


def test_if_safe_record_exposes_canon_fields() -> None:
    record_fields = {field.name for field in fields(SafeStateRecord)}

    assert record_fields == {
        "SAFE_state",
        "SAFE_reason",
        "blocked_commands",
        "allowed_commands",
        "exit_conditions",
        "power_state",
        "thermal_state",
        "sensor_state",
        "bayonet_state",
        "damage_state",
        "timestamp",
        "reason_codes",
        "blackbox_relevance",
    }


def test_if_safe_mapper_defaults_unknown_not_inactive() -> None:
    record = safe_state_from_runtime_state()

    assert record.SAFE_state == "safe_unknown"
    assert record.SAFE_reason == "missing"
    assert record.power_state == "unknown"
    assert record.thermal_state == "unknown"
    assert record.sensor_state == "unknown"
    assert record.reason_codes == ()
    assert record.blackbox_relevance is False


def test_if_safe_mapper_detects_low_power_and_cap() -> None:
    record = safe_state_from_runtime_state(
        power={"soc_pct": 4.0, "supercap_soc_pct": 3.0, "loads_w": {"rcs": 10.0}},
        timestamp=21.0,
    )

    assert record.SAFE_state == "safe_limited"
    assert record.SAFE_reason == "SAFE_POWER_LOW"
    assert record.power_state == "low"
    assert record.timestamp == 21.0
    assert record.reason_codes == ("SAFE_POWER_LOW", "SAFE_CAP_LOW")
    assert "exit_power_recovered" in record.exit_conditions


def test_if_safe_mapper_detects_critical_thermal_lockdown() -> None:
    record = safe_state_from_runtime_state(
        thermal={"nodes": [{"id": "pdu", "temp_c": 95.0, "warn_c": 70.0, "tripped": True}]},
    )

    assert record.SAFE_state == "safe_lockdown"
    assert record.SAFE_reason == "SAFE_THERMAL_CRITICAL"
    assert record.thermal_state == "critical"
    assert "SAFE_THERMAL_CRITICAL" in record.reason_codes
    assert "radar" in record.blocked_commands
    assert record.blackbox_relevance is True


def test_if_safe_mapper_detects_sensor_conflict_warning() -> None:
    record = safe_state_from_runtime_state(
        sensor_records=[
            {"sensor_id": "imu", "trust_status": "conflicting", "reason_codes": ("SENSOR_CONFLICTING",)}
        ],
    )

    assert record.SAFE_state == "safe_warning"
    assert record.SAFE_reason == "SAFE_SENSOR_CONFLICT"
    assert record.sensor_state == "conflicting"
    assert record.reason_codes == ("SAFE_SENSOR_CONFLICT",)


def test_if_safe_mapper_detects_pdu_fault_limited() -> None:
    record = safe_state_from_runtime_state(
        pdu_permissions=[
            {"load_id": "nbl", "allowance_state": "load_rejected", "reason_codes": ("PDU_OVERLOAD",)}
        ],
    )

    assert record.SAFE_state == "safe_limited"
    assert record.SAFE_reason == "SAFE_PDU_FAULT"
    assert record.reason_codes == ("SAFE_PDU_FAULT",)
    assert "nbl" in record.blocked_commands
