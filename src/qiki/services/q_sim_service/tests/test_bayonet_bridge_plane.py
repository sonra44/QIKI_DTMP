from dataclasses import fields

from qiki.services.q_sim_service.core.world_model import (
    BayonetBridgeRecord,
    bayonet_bridge_from_runtime_state,
    bayonet_mech_from_docking_state,
)


def _ready_mech():
    return bayonet_mech_from_docking_state(
        {
            "enabled": True,
            "state": "structural_check_passed",
            "connected": True,
            "connected_object_id": "module:arm",
            "structural_rating": "passed",
        }
    )


def test_if_bayonet_bridge_record_exposes_canon_fields() -> None:
    record_fields = {field.name for field in fields(BayonetBridgeRecord)}

    assert record_fields == {
        "bayonet_id",
        "connected_object_id",
        "bridge_state",
        "mechanical_state",
        "structural_check",
        "electrical_safety_state",
        "umbilical_state",
        "passport_state",
        "power_direction",
        "power_limit_W",
        "data_link_state",
        "thermal_node",
        "reason_codes",
    }


def test_if_bayonet_bridge_defaults_disallowed_without_chain() -> None:
    record = bayonet_bridge_from_runtime_state(None)

    assert record.bridge_state == "bridge_disallowed"
    assert record.mechanical_state == "unknown"
    assert record.structural_check == "missing"
    assert record.electrical_safety_state == "missing"
    assert record.passport_state == "missing"
    assert record.reason_codes == (
        "BRIDGE_HARD_LOCK_MISSING",
        "BRIDGE_STRUCTURAL_CHECK_MISSING",
        "BRIDGE_ELECTRICAL_UNSAFE",
        "BRIDGE_UMBILICAL_MISSING",
        "BRIDGE_PASSPORT_MISSING",
        "BRIDGE_PDU_DENIED",
    )


def test_if_bayonet_bridge_hard_lock_without_structural_is_disallowed() -> None:
    mech = bayonet_mech_from_docking_state({"enabled": True, "state": "docked", "connected": True})
    record = bayonet_bridge_from_runtime_state(mech)

    assert record.mechanical_state == "mechanical_hard_lock"
    assert record.structural_check == "missing"
    assert record.bridge_state == "bridge_disallowed"
    assert "BRIDGE_STRUCTURAL_CHECK_MISSING" in record.reason_codes


def test_if_bayonet_bridge_full_chain_allows_bridge() -> None:
    record = bayonet_bridge_from_runtime_state(
        _ready_mech(),
        electrical_safety_state="passed",
        umbilical_state="mated",
        passport_state="validated",
        pdu_allowance_state="allowed",
        thermal_clearance="clear",
        power_direction="module_to_body",
        power_limit_W=120.0,
        data_link_state="online",
    )

    assert record.bridge_state == "bridge_allowed"
    assert record.connected_object_id == "module:arm"
    assert record.structural_check == "passed"
    assert record.reason_codes == ()


def test_if_bayonet_bridge_active_restricted_motion_degrades() -> None:
    record = bayonet_bridge_from_runtime_state(
        _ready_mech(),
        desired_bridge_state="bridge_active",
        electrical_safety_state="passed",
        umbilical_state="mated",
        passport_state="validated",
        pdu_allowance_state="allowed",
        thermal_clearance="clear",
        motion_restriction="restricted",
    )

    assert record.bridge_state == "bridge_degraded"
    assert record.reason_codes == ("BRIDGE_ACTIVE_RESTRICTED_MOTION",)


def test_if_bayonet_bridge_surfaces_thermal_pdu_safe_blockers() -> None:
    record = bayonet_bridge_from_runtime_state(
        _ready_mech(),
        electrical_safety_state="passed",
        umbilical_state="mated",
        passport_state="validated",
        pdu_allowance_state="denied",
        thermal_clearance="blocked",
        safe_state="safe_lockdown",
        thermal_node="bayonet",
    )

    assert record.bridge_state == "bridge_disallowed"
    assert record.thermal_node == "bayonet"
    assert record.reason_codes == (
        "BRIDGE_PDU_DENIED",
        "BRIDGE_THERMAL_BLOCK",
        "BRIDGE_SAFE_BLOCK",
    )
