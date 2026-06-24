"""RCS control via COMMANDS_CONTROL (no new proto) — no-mocks."""

from __future__ import annotations

from dataclasses import fields

from qiki.services.q_sim_service.core.world_model import (
    RcsCommandRecord,
    rcs_command_from_runtime_state,
)
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.core import CommandMessage, MessageMetadata


def test_sim_rcs_fire_and_stop_control_commands() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")

    fire = CommandMessage(
        command_name="sim.rcs.fire",
        parameters={"axis": "port", "pct": 60.0, "duration_s": 2.0},
        metadata=meta,
    )
    assert qsim.apply_control_command(fire) is True

    qsim.step()
    state = qsim.world_model.get_state()
    rcs = (state.get("propulsion") or {}).get("rcs") or {}
    assert rcs.get("enabled") is True
    assert rcs.get("active") in (True, False)  # must exist
    assert float(rcs.get("command_pct", 0.0)) > 0.0
    assert float(rcs.get("time_left_s", 0.0)) <= 2.0 + 1e-6

    stop = CommandMessage(command_name="sim.rcs.stop", parameters={}, metadata=meta)
    assert qsim.apply_control_command(stop) is True

    qsim.step()
    state2 = qsim.world_model.get_state()
    rcs2 = (state2.get("propulsion") or {}).get("rcs") or {}
    assert float(rcs2.get("command_pct", 0.0)) == 0.0


def test_if_rcs_cmd_record_exposes_canon_fields() -> None:
    record_fields = {field.name for field in fields(RcsCommandRecord)}

    assert record_fields == {
        "command_id",
        "RCS_mode",
        "requested_delta_v",
        "requested_torque",
        "duration_s",
        "active_clusters",
        "required_thrusters",
        "SoC_cap_required",
        "thermal_nodes",
        "working_mass_required",
        "CoM_class",
        "inertia_class",
        "bayonet_state",
        "bridge_state",
        "Thrust_Map_status",
        "Torque_Map_status",
        "validation_status",
        "reason_codes",
    }


def test_if_rcs_cmd_mapper_projects_real_fire_request_without_effect_claim() -> None:
    qsim = QSimService(QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO"))
    qsim.world_model.set_dock_connected(False)
    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")
    fire = CommandMessage(
        command_name="sim.rcs.fire",
        parameters={"axis": "forward", "pct": 60.0, "duration_s": 2.0},
        metadata=meta,
    )
    assert qsim.apply_control_command(fire) is True
    qsim.step(delta_time=1.0)
    state = qsim.world_model.get_state()

    record = rcs_command_from_runtime_state(
        (state.get("propulsion") or {}).get("rcs"),
        power=state.get("power"),
        thermal=state.get("thermal"),
        docking=state.get("docking"),
        command_id="cmd-rcs-forward",
        requested_delta_v={"axis": "forward", "pct": 60.0},
        duration_s=2.0,
    )

    assert record.command_id == "cmd-rcs-forward"
    assert record.RCS_mode == "forward"
    assert record.duration_s == 2.0
    assert record.Thrust_Map_status == "available"
    assert record.Torque_Map_status == "available"
    assert record.validation_status == "allowed"
    assert record.required_thrusters
    assert record.active_clusters
    assert record.reason_codes == ()


def test_if_rcs_cmd_mapper_marks_missing_maps_rejected() -> None:
    record = rcs_command_from_runtime_state(
        {"enabled": True, "active": False, "axis": "forward", "thrusters": []},
        command_id="cmd-no-map",
        requested_delta_v={"axis": "forward"},
        duration_s=1.0,
    )

    assert record.validation_status == "rejected"
    assert record.Thrust_Map_status == "missing"
    assert record.Torque_Map_status == "missing"
    assert "THRUST_MAP_MISSING" in record.reason_codes
    assert "TORQUE_MAP_MISSING" in record.reason_codes


def test_if_rcs_cmd_mapper_surfaces_cap_low_and_thermal_block() -> None:
    record = rcs_command_from_runtime_state(
        {
            "enabled": True,
            "active": True,
            "axis": "port",
            "thrusters": [{"index": 1, "cluster_id": "rcs-a"}],
        },
        power={"supercap_soc_pct": 0.0},
        thermal={"nodes": [{"id": "rcs_cluster_a", "temp_c": 80.0, "warn_c": 60.0, "tripped": True}]},
        command_id="cmd-blocked",
        requested_delta_v={"axis": "port"},
        duration_s=1.0,
    )

    assert record.validation_status == "rejected"
    assert "CAP_LOW" in record.reason_codes
    assert "RCS_CLUSTER_HOT" in record.reason_codes


def test_if_rcs_cmd_mapper_surfaces_bridge_active_restricted_motion() -> None:
    record = rcs_command_from_runtime_state(
        {
            "enabled": True,
            "active": True,
            "axis": "forward",
            "propellant_kg": 1.0,
            "thrusters": [{"index": 1, "cluster_id": "rcs-a"}],
        },
        power={"dock_connected": True, "supercap_soc_pct": 80.0},
        docking={"state": "docked"},
        command_id="cmd-bridge",
        requested_delta_v={"axis": "forward"},
        duration_s=1.0,
    )

    assert record.validation_status == "rejected"
    assert record.bridge_state == "active_unrated"
    assert "BRIDGE_ACTIVE_RESTRICTED_MOTION" in record.reason_codes
