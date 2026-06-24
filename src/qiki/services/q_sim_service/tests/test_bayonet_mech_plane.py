from dataclasses import fields

from qiki.services.q_sim_service.core.world_model import (
    BayonetMechRecord,
    bayonet_mech_from_docking_state,
)


def test_if_bayonet_mech_record_exposes_canon_fields_plus_reason_codes() -> None:
    record_fields = {field.name for field in fields(BayonetMechRecord)}

    assert {
        "bayonet_id",
        "state",
        "state_timestamp",
        "state_source",
        "lock_quality",
        "structural_rating",
        "degraded_reason",
        "connected_object_id",
        "mechanical_load_class",
        "emergency_detach_available",
    }.issubset(record_fields)
    assert "reason_codes" in record_fields


def test_if_bayonet_mech_mapper_defaults_unknown_not_free_or_locked() -> None:
    record = bayonet_mech_from_docking_state(None)

    assert record.state == "unknown"
    assert record.lock_quality == "unknown"
    assert record.structural_rating == "unknown"
    assert record.connected_object_id == "unknown"
    assert record.emergency_detach_available is False
    assert record.reason_codes == ("BAYONET_STATE_UNKNOWN",)


def test_if_bayonet_mech_mapper_maps_undocked_to_detached() -> None:
    record = bayonet_mech_from_docking_state({"enabled": True, "state": "undocked", "connected": False})

    assert record.state == "detached"
    assert record.connected_object_id == "none"
    assert record.reason_codes == ()


def test_if_bayonet_mech_mapper_docked_is_hard_lock_but_not_structural_passed() -> None:
    record = bayonet_mech_from_docking_state(
        {"enabled": True, "state": "docked", "connected": True, "port": "B"},
        timestamp=42.0,
    )

    assert record.state == "mechanical_hard_lock"
    assert record.state_timestamp == 42.0
    assert record.connected_object_id == "dock:B"
    assert record.lock_quality == "hard_lock_observed"
    assert record.structural_rating == "unknown"
    assert record.reason_codes == ()


def test_if_bayonet_mech_mapper_soft_capture_does_not_claim_hard_lock() -> None:
    record = bayonet_mech_from_docking_state(
        {"enabled": True, "state": "soft_capture", "connected": True, "port": "A"}
    )

    assert record.state == "soft_capture"
    assert record.lock_quality == "soft_capture"
    assert record.structural_rating == "unknown"
    assert record.emergency_detach_available is True
    assert record.reason_codes == ("BAYONET_SOFT_CAPTURE_ONLY", "BAYONET_HARD_LOCK_MISSING")


def test_if_bayonet_mech_mapper_degraded_lock_is_restricted() -> None:
    record = bayonet_mech_from_docking_state(
        {
            "enabled": True,
            "state": "degraded_lock",
            "connected": True,
            "connected_object_id": "module:arm",
            "degraded_reason": "latch_sensor_disagree",
        }
    )

    assert record.state == "degraded_lock"
    assert record.connected_object_id == "module:arm"
    assert record.degraded_reason == "latch_sensor_disagree"
    assert record.reason_codes == ("BAYONET_DEGRADED_LOCK",)
