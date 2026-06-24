from dataclasses import fields

import pytest

from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import Unit as ProtoUnit
from qiki.services.q_sim_service.core.world_model import (
    NblPacketRecord,
    PduPermissionRecord,
    PowerTelemetryRecord,
    WorldModel,
    nbl_packet_from_runtime_state,
    pdu_permissions_from_power_state,
    power_telemetry_from_power_state,
)
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.models.telemetry import TelemetrySnapshotModel

RCS_PORT_ID = "e03efa3e-5735-5a82-8f5c-9a9d9dfff351"


def test_power_telemetry_includes_power_plane_fields() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    payload = qsim._build_telemetry_payload(qsim.world_model.get_state())
    normalized = TelemetrySnapshotModel.normalize_payload(payload)

    power = normalized.get("power")
    assert isinstance(power, dict)

    # Supervisor / PDU / supercap fields (no v2, still under power.*).
    assert "loads_w" in power
    assert "sources_w" in power
    assert isinstance(power.get("loads_w"), dict)
    assert isinstance(power.get("sources_w"), dict)
    assert "battery_charge_w" in power
    assert "battery_discharge_w" in power
    assert "battery_spill_w" in power
    assert "battery_unserved_w" in power
    assert "battery_1_voltage_v" in power
    assert "battery_2_voltage_v" in power
    assert "shed_reasons" in power
    assert "pdu_limit_w" in power
    assert "pdu_throttled" in power
    assert "throttled_loads" in power
    assert "faults" in power
    assert "supercap_soc_pct" in power
    assert "battery_capacity_wh" in power
    assert "supercap_capacity_wh" in power
    assert "supercap_charge_w" in power
    assert "supercap_discharge_w" in power
    assert "dock_connected" in power
    assert "dock_soft_start_pct" in power
    assert "dock_power_w" in power
    assert "dock_v" in power
    assert "dock_a" in power
    assert "dock_temp_c" in power
    assert "nbl_active" in power
    assert "nbl_allowed" in power
    assert "nbl_power_w" in power
    assert "nbl_budget_w" in power
    assert isinstance(power.get("battery_1_voltage_v"), float)
    assert isinstance(power.get("battery_2_voltage_v"), float)


def test_if_power_telem_record_exposes_canon_fields_separately() -> None:
    record_fields = {field.name for field in fields(PowerTelemetryRecord)}

    assert {
        "battery_soc_pct",
        "battery_capacity_Wh",
        "battery_charge_W",
        "battery_discharge_W",
        "battery_temp_state",
        "supercap_soc_pct",
        "supercap_capacity_Wh",
        "supercap_charge_W",
        "supercap_discharge_W",
        "supercap_temp_state",
        "source_generation_W",
        "bus_voltage_V",
        "bus_current_A",
        "loads_W",
        "spill_W",
        "unserved_W",
        "timestamp",
        "freshness",
        "source",
        "trust_status",
        "reason_codes",
    } <= record_fields


def test_if_power_telem_mapper_keeps_battery_and_supercap_separate() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 100.0,
            "battery_soc_init_pct": 42.0,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "base_power_in_w": 40.0,
                "base_power_out_w": 10.0,
                "supercap_capacity_wh": 5.0,
                "supercap_soc_pct_init": 70.0,
                "supercap_max_charge_w": 120.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    wm.step(1.0)

    record = power_telemetry_from_power_state(
        wm.get_state()["power"],
        timestamp=wm.sim_time_epoch_ts(),
        freshness="fresh",
    )

    assert record.battery_soc_pct == pytest.approx(wm.battery_level)
    assert record.supercap_soc_pct == pytest.approx(wm.supercap_soc_pct)
    assert record.battery_soc_pct != pytest.approx(record.supercap_soc_pct)
    assert record.battery_capacity_Wh == pytest.approx(100.0)
    assert record.supercap_capacity_Wh == pytest.approx(5.0)
    assert record.battery_temp_state == "missing"
    assert record.supercap_temp_state == "missing"
    assert record.trust_status == "trusted"
    assert record.source == "q_sim_service.world_model.power"
    assert "POWER_TELEM_MISSING" not in record.reason_codes


def test_if_power_telem_mapper_marks_incomplete_power_state_missing() -> None:
    record = power_telemetry_from_power_state({"soc_pct": 42.0}, freshness="unknown")

    assert record.battery_soc_pct == pytest.approx(42.0)
    assert record.supercap_soc_pct is None
    assert record.trust_status == "missing"
    assert record.reason_codes == ("POWER_TELEM_MISSING",)
    assert record.freshness == "unknown"


def test_if_pdu_power_record_exposes_canon_fields() -> None:
    record_fields = {field.name for field in fields(PduPermissionRecord)}

    assert {
        "load_id",
        "load_class",
        "requested_power_W",
        "peak_required",
        "duration_s",
        "SoC_bat",
        "SoC_cap",
        "bus_voltage_V",
        "bus_current_A",
        "PDU_state",
        "thermal_clearance",
        "SAFE_state",
        "allowance_state",
        "reason_codes",
    } <= record_fields


def test_if_nbl_record_exposes_canon_fields_and_status() -> None:
    record_fields = {field.name for field in fields(NblPacketRecord)}

    assert {
        "packet_id",
        "criticality",
        "payload_class",
        "payload_size_bits",
        "transmit_attempts",
        "SoC_cap_cost",
        "power_cost",
        "thermal_node",
        "expected_latency",
        "delivery_confidence",
        "audit_required",
        "blackbox_relevance",
        "reason_codes",
    } <= record_fields
    assert "status" in record_fields


def test_if_nbl_mapper_defaults_to_rules_only_not_sent() -> None:
    record = nbl_packet_from_runtime_state(None)

    assert record.status == "not_implemented"
    assert record.delivery_confidence == "unknown"
    assert record.reason_codes == ("NBL_NOT_IMPLEMENTED", "NBL_RULES_ONLY")
    assert record.blackbox_relevance is False


def test_if_nbl_mapper_rejects_non_critical_packet() -> None:
    record = nbl_packet_from_runtime_state(
        {"nbl_active": True, "nbl_allowed": True, "nbl_budget_w": 20.0, "supercap_soc_pct": 60.0},
        packet_id="pkt-chatty",
        criticality="routine",
        payload_class="bulk_telemetry",
        payload_size_bits=128,
    )

    assert record.status == "packet_rejected"
    assert "NBL_NOT_CRITICAL" in record.reason_codes
    assert "NBL_RULES_ONLY" in record.reason_codes
    assert record.delivery_confidence == "unknown"


def test_if_nbl_mapper_allows_critical_packet_but_does_not_fake_delivery() -> None:
    record = nbl_packet_from_runtime_state(
        {"nbl_active": True, "nbl_allowed": True, "nbl_budget_w": 20.0, "supercap_soc_pct": 60.0},
        packet_id="pkt-distress",
        criticality="emergency",
        payload_class="distress_packet",
        payload_size_bits=128,
    )

    assert record.status == "packet_allowed"
    assert record.audit_required is True
    assert record.blackbox_relevance is True
    assert record.delivery_confidence == "unknown"
    assert record.reason_codes == ("NBL_RULES_ONLY",)


def test_if_nbl_soc_cap_cost_does_not_reuse_current_supercap_soc() -> None:
    record = nbl_packet_from_runtime_state(
        {"nbl_active": True, "nbl_allowed": True, "nbl_budget_w": 20.0, "supercap_soc_pct": 60.0},
        packet_id="pkt-cost",
        criticality="emergency",
        payload_class="distress_packet",
        payload_size_bits=128,
    )

    assert record.SoC_cap_cost is None


def test_if_nbl_mapper_surfaces_cap_low_and_thermal_block() -> None:
    record = nbl_packet_from_runtime_state(
        {"nbl_active": True, "nbl_allowed": False, "nbl_budget_w": 0.0, "supercap_soc_pct": 0.0},
        thermal={"nodes": [{"id": "core", "temp_c": 95.0, "warn_c": 70.0, "tripped": True}]},
        packet_id="pkt-blocked",
        criticality="emergency",
        payload_class="distress_packet",
        payload_size_bits=128,
    )

    assert record.status == "packet_rejected"
    assert "NBL_CAP_LOW" in record.reason_codes
    assert "NBL_THERMAL_BLOCK" in record.reason_codes


def test_if_pdu_power_mapper_projects_real_shed_and_throttle_gates() -> None:
    records = pdu_permissions_from_power_state(
        {
            "loads_w": {"radar": 120.0, "rcs": 40.0},
            "soc_pct": 55.0,
            "supercap_soc_pct": 12.0,
            "bus_v": 28.0,
            "bus_a": 7.0,
            "load_shedding": True,
            "shed_loads": ["radar"],
            "shed_reasons": ["pdu_overcurrent"],
            "pdu_throttled": True,
            "throttled_loads": ["rcs"],
            "faults": ["PDU_OVERCURRENT"],
        },
        thermal={"nodes": [{"id": "pdu", "tripped": True}]},
        duration_s=2.5,
    )

    by_load = {record.load_id: record for record in records}
    radar = by_load["radar"]
    assert radar.load_class == "sensor"
    assert radar.requested_power_W == pytest.approx(120.0)
    assert radar.peak_required is False
    assert radar.duration_s == pytest.approx(2.5)
    assert radar.SoC_bat == pytest.approx(55.0)
    assert radar.SoC_cap == pytest.approx(12.0)
    assert radar.bus_voltage_V == pytest.approx(28.0)
    assert radar.bus_current_A == pytest.approx(7.0)
    assert radar.PDU_state == "overcurrent"
    assert radar.thermal_clearance == "blocked"
    assert radar.SAFE_state == "unknown"
    assert radar.allowance_state == "load_shed"
    assert radar.reason_codes == ("PDU_OVERLOAD", "LOAD_SHED_ACTIVE", "THERMAL_BLOCK")

    rcs = by_load["rcs"]
    assert rcs.load_class == "peak"
    assert rcs.peak_required is True
    assert rcs.thermal_clearance == "clear"
    assert rcs.allowance_state == "load_allowed_limited"
    assert rcs.reason_codes == ("PDU_OVERLOAD",)


def test_if_pdu_power_mapper_marks_missing_power_degraded() -> None:
    records = pdu_permissions_from_power_state({}, thermal=None)

    assert len(records) == 1
    record = records[0]
    assert record.load_id == "missing"
    assert record.load_class == "missing"
    assert record.requested_power_W is None
    assert record.peak_required is False
    assert record.SoC_bat is None
    assert record.SoC_cap is None
    assert record.bus_voltage_V is None
    assert record.bus_current_A is None
    assert record.PDU_state == "missing"
    assert record.thermal_clearance == "missing"
    assert record.allowance_state == "load_degraded"
    assert record.reason_codes == ("PDU_DENIED",)


def test_if_pdu_power_mapper_keeps_thermal_clearance_missing_without_source() -> None:
    records = pdu_permissions_from_power_state(
        {
            "loads_w": {"radar": 10.0},
            "soc_pct": 80.0,
            "supercap_soc_pct": 50.0,
            "bus_v": 28.0,
            "bus_a": 1.0,
        },
        thermal=None,
    )

    assert records[0].thermal_clearance == "missing"
    assert records[0].allowance_state == "load_allowed"


def test_telemetry_battery_is_legacy_alias_of_power_soc_pct() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    payload = qsim._build_telemetry_payload(qsim.world_model.get_state())
    normalized = TelemetrySnapshotModel.normalize_payload(payload)

    assert normalized.get("battery") == pytest.approx(((normalized.get("power") or {}).get("soc_pct")))


def test_battery_soc_init_pct_is_applied_and_clamped() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "battery_soc_init_pct": 42.5,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    assert wm.battery_level == pytest.approx(42.5)

    bot_config["hardware_profile"]["battery_soc_init_pct"] = 120.0
    wm = WorldModel(bot_config=bot_config)
    assert wm.battery_level == pytest.approx(100.0)

    bot_config["hardware_profile"]["battery_soc_init_pct"] = -10.0
    wm = WorldModel(bot_config=bot_config)
    assert wm.battery_level == pytest.approx(0.0)


def test_soc_changes_from_net_power_and_capacity_wh() -> None:
    # Deficit: 100W for 1 hour on a 100Wh battery drains 100% -> 0%.
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 100.0,
            "battery_soc_init_pct": 100.0,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": 0.0,
                "base_power_out_w": 100.0,
                "motion_power_w_per_mps": 0.0,
                "mcqpu_power_w_at_100pct": 0.0,
                "radar_power_w": 0.0,
                "transponder_power_w": 0.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    wm.set_runtime_load_inputs(
        radar_enabled=False,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=False,
    )
    wm.step(3600.0)
    assert wm.battery_level == pytest.approx(0.0)

    # Surplus: 100W for 1 hour on a 100Wh battery charges 0% -> 100% (clamped).
    bot_config["hardware_profile"]["battery_soc_init_pct"] = 0.0
    bot_config["hardware_profile"]["power_plane"]["base_power_in_w"] = 100.0
    bot_config["hardware_profile"]["power_plane"]["base_power_out_w"] = 0.0
    wm = WorldModel(bot_config=bot_config)
    wm.set_runtime_load_inputs(
        radar_enabled=False,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=False,
    )
    wm.step(3600.0)
    assert wm.battery_level == pytest.approx(100.0)


def test_battery_charge_limit_clamps_soc_and_reports_spill() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 100.0,
            "battery_soc_init_pct": 0.0,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": 100.0,
                "base_power_out_w": 0.0,
                "battery_max_charge_w": 10.0,
                "battery_max_discharge_w": 0.0,
                "motion_power_w_per_mps": 0.0,
                "mcqpu_power_w_at_100pct": 0.0,
                "radar_power_w": 0.0,
                "transponder_power_w": 0.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    wm.set_runtime_load_inputs(
        radar_enabled=False,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=False,
    )
    wm.step(3600.0)
    assert wm.battery_level == pytest.approx(10.0)
    state = wm.get_state()
    power = state["power"]
    assert float(power["battery_charge_w"]) == pytest.approx(10.0)
    assert float(power["battery_spill_w"]) == pytest.approx(90.0)


def test_battery_discharge_limit_clamps_soc_and_reports_unserved() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 100.0,
            "battery_soc_init_pct": 100.0,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": 0.0,
                "base_power_out_w": 100.0,
                "battery_max_charge_w": 0.0,
                "battery_max_discharge_w": 10.0,
                "motion_power_w_per_mps": 0.0,
                "mcqpu_power_w_at_100pct": 0.0,
                "radar_power_w": 0.0,
                "transponder_power_w": 0.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    wm.set_runtime_load_inputs(
        radar_enabled=False,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=False,
    )
    wm.step(3600.0)
    assert wm.battery_level == pytest.approx(90.0)
    state = wm.get_state()
    power = state["power"]
    assert float(power["battery_discharge_w"]) == pytest.approx(10.0)
    assert float(power["battery_unserved_w"]) == pytest.approx(90.0)
    assert "BATTERY_DISCHARGE_LIMIT" in wm.power_faults


def test_power_breakdown_is_consistent_with_power_in_out() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 100.0,
            "battery_soc_init_pct": 50.0,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": 10.0,
                "base_power_out_w": 20.0,
                "motion_power_w_per_mps": 40.0,
                "mcqpu_power_w_at_100pct": 0.0,
                "radar_power_w": 0.0,
                "transponder_power_w": 0.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    wm.speed = 1.0
    wm.set_runtime_load_inputs(
        radar_enabled=False,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=False,
    )
    wm.step(1.0)
    state = wm.get_state()
    power = state["power"]
    loads = power["loads_w"]
    sources = power["sources_w"]

    assert sum(float(v) for v in loads.values()) == pytest.approx(float(power["power_out_w"]))
    assert sum(float(v) for v in sources.values()) == pytest.approx(float(power["power_in_w"]))


def test_soc_load_shedding_hysteresis_blocks_non_critical_loads() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "soc_shed_low_pct": 20.0,
                "soc_shed_high_pct": 30.0,
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    wm.set_runtime_load_inputs(
        radar_enabled=True,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=True,
    )

    wm.battery_level = 19.0
    wm.step(1.0)
    assert wm.radar_allowed is False
    assert wm.transponder_allowed is False
    assert "radar" in wm.power_shed_loads
    assert "transponder" in wm.power_shed_loads
    assert "low_soc" in wm.power_shed_reasons

    # Between low and high threshold we should remain in shed state (hysteresis).
    wm.battery_level = 25.0
    wm.step(1.0)
    assert wm.radar_allowed is False
    assert wm.transponder_allowed is False

    # Above high threshold shedding clears.
    wm.battery_level = 31.0
    wm.step(1.0)
    assert wm.radar_allowed is True
    assert wm.transponder_allowed is True


def test_pdu_overcurrent_throttles_motion_to_limit() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 0.5,  # 14 W limit
                "base_power_in_w": 0.0,
                "base_power_out_w": 5.0,
                "motion_power_w_per_mps": 40.0,
                "mcqpu_power_w_at_100pct": 0.0,
                "radar_power_w": 0.0,
                "transponder_power_w": 0.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    wm.speed = 1.0
    wm.set_runtime_load_inputs(
        radar_enabled=False,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=False,
    )
    wm.step(1.0)

    assert wm.power_pdu_throttled is True
    assert "motion" in wm.power_throttled_loads
    assert wm.power_bus_a <= 0.5 + 1e-6


def test_pdu_overcurrent_sheds_noncritical_loads_in_deterministic_order() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 0.2,  # 5.6 W limit
                "base_power_in_w": 0.0,
                "base_power_out_w": 0.0,
                "motion_power_w_per_mps": 0.0,
                "mcqpu_power_w_at_100pct": 0.0,
                "radar_power_w": 18.0,
                "transponder_power_w": 6.0,
                "nbl_active_init": True,
                "nbl_max_power_w": 20.0,
                "nbl_soc_min_pct": 0.0,
                "nbl_core_temp_max_c": 120.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    wm.battery_level = 99.0
    wm.temp_core_c = 25.0
    wm.set_runtime_load_inputs(
        radar_enabled=True,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=True,
    )
    wm.step(1.0)

    assert wm.power_shed_loads[:3] == ["nbl", "radar", "transponder"]
    assert "pdu_overcurrent" in wm.power_shed_reasons
    assert wm.nbl_allowed is False
    assert wm.nbl_power_w == pytest.approx(0.0)
    assert wm.radar_allowed is False
    assert wm.transponder_allowed is False
    assert wm.power_pdu_throttled is False
    assert wm.power_bus_a <= 0.2 + 1e-6


def test_pdu_overcurrent_throttles_rcs_and_marks_load() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 0.2,  # 5.6 W limit
                "base_power_in_w": 0.0,
                "base_power_out_w": 0.0,
                "motion_power_w_per_mps": 0.0,
                "mcqpu_power_w_at_100pct": 0.0,
                "radar_power_w": 0.0,
                "transponder_power_w": 0.0,
            },
            "actuators": [
                {"id": RCS_PORT_ID, "role": "rcs_port", "type": "rcs_thruster"},
            ],
            "propulsion_plane": {
                "enabled": True,
                "thrusters_path": "config/propulsion/thrusters.json",
                "propellant_kg_init": 1.0,
                "isp_s": 60.0,
                "rcs_power_w_at_100pct": 80.0,
                "heat_fraction_to_hull": 0.0,
                "pulse_window_s": 0.25,
                "ztt_torque_tol_nm": 25.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    cmd = ActuatorCommand()
    cmd.actuator_id.value = RCS_PORT_ID
    cmd.command_type = ActuatorCommand.CommandType.SET_VELOCITY
    cmd.float_value = 100.0
    cmd.unit = ProtoUnit.PERCENT
    cmd.timeout_ms = 2000
    wm.update(cmd)
    wm.step(1.0)

    assert wm.power_pdu_throttled is True
    assert "rcs" in wm.power_throttled_loads
    assert wm.rcs_throttled is True
    assert wm.power_bus_a <= 0.2 + 1e-6


@pytest.mark.parametrize("mode", ["charge", "discharge"])
def test_supercap_charges_and_discharges(mode: str) -> None:
    if mode == "charge":
        base_in_w = 100.0
        base_out_w = 0.0
        init_soc = 0.0
    else:
        base_in_w = 0.0
        base_out_w = 100.0
        init_soc = 100.0

    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": base_in_w,
                "base_power_out_w": base_out_w,
                "supercap_capacity_wh": 5.0,
                "supercap_soc_pct_init": init_soc,
                "supercap_max_charge_w": 120.0,
                "supercap_max_discharge_w": 200.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    wm.set_runtime_load_inputs(
        radar_enabled=False,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=False,
    )
    wm.step(1.0)

    if mode == "charge":
        assert wm.supercap_charge_w > 0.0
        assert wm.supercap_discharge_w == 0.0
    else:
        assert wm.supercap_discharge_w > 0.0
        assert wm.supercap_charge_w == 0.0


def test_dock_power_bridge_soft_start_ramps_input() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": 0.0,
                "base_power_out_w": 0.0,
                "dock_connected_init": True,
                "dock_station_bus_v": 28.0,
                "dock_station_max_power_w": 280.0,
                "dock_current_limit_a": 10.0,
                "dock_soft_start_s": 2.0,
                "dock_temp_c_init": -60.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    wm.set_runtime_load_inputs(
        radar_enabled=False,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=False,
    )

    wm.step(1.0)
    p1 = float(wm.dock_power_w)
    assert 0.0 < p1 < 280.0
    assert 40.0 <= wm.dock_soft_start_pct <= 60.0

    wm.step(1.0)
    p2 = float(wm.dock_power_w)
    assert p2 > p1
    assert wm.dock_soft_start_pct >= 99.0


def test_nbl_budgeter_blocks_when_soc_low() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": 0.0,
                "base_power_out_w": 0.0,
                "nbl_active_init": True,
                "nbl_max_power_w": 120.0,
                "nbl_soc_min_pct": 35.0,
                "nbl_core_temp_max_c": 90.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    wm.battery_level = 20.0
    wm.step(1.0)
    assert wm.nbl_active is True
    assert wm.nbl_allowed is False
    assert wm.nbl_power_w == 0.0
    assert "nbl" in wm.power_shed_loads
    assert "nbl_budget" in wm.power_shed_reasons


def test_nbl_budgeter_allows_when_soc_ok() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": 200.0,
                "base_power_out_w": 0.0,
                "nbl_active_init": True,
                "nbl_max_power_w": 120.0,
                "nbl_soc_min_pct": 35.0,
                "nbl_core_temp_max_c": 90.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    wm.battery_level = 99.0
    wm.temp_core_c = 25.0
    wm.step(1.0)
    assert wm.nbl_active is True
    assert wm.nbl_allowed is True
    assert wm.nbl_power_w > 0.0


def test_control_commands_toggle_dock_and_nbl() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": 0.0,
                "base_power_out_w": 0.0,
                "dock_connected_init": True,
                "dock_station_bus_v": 28.0,
                "dock_station_max_power_w": 280.0,
                "dock_current_limit_a": 10.0,
                "dock_soft_start_s": 2.0,
                "dock_temp_c_init": -60.0,
                "nbl_active_init": False,
                "nbl_max_power_w": 20.0,
                "nbl_soc_min_pct": 10.0,
                "nbl_core_temp_max_c": 90.0,
            },
        }
    }

    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)
    qsim.world_model = WorldModel(bot_config=bot_config)
    qsim.world_model.battery_level = 99.0
    qsim.world_model.temp_core_c = 25.0
    qsim.world_model.set_runtime_load_inputs(
        radar_enabled=False,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=False,
    )

    # Dock starts connected and ramps in.
    qsim.world_model.step(1.0)
    assert qsim.world_model.dock_connected is True
    assert qsim.world_model.dock_soft_start_pct > 0.0
    assert qsim.world_model.dock_power_w > 0.0

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")

    # Turn dock off: should reset bridge state.
    dock_off = CommandMessage(command_name="power.dock.off", parameters={}, metadata=meta)
    assert qsim.apply_control_command(dock_off) is True
    assert qsim.world_model.dock_connected is False
    assert qsim.world_model.dock_soft_start_pct == 0.0
    assert qsim.world_model.dock_power_w == 0.0

    # Turn dock back on: soft start restarts.
    dock_on = CommandMessage(command_name="power.dock.on", parameters={}, metadata=meta)
    assert qsim.apply_control_command(dock_on) is True
    assert qsim.world_model.dock_connected is True
    qsim.world_model.step(1.0)
    assert 0.0 < qsim.world_model.dock_soft_start_pct < 100.0
    assert qsim.world_model.dock_power_w > 0.0

    # Turn NBL on.
    nbl_on = CommandMessage(command_name="power.nbl.on", parameters={}, metadata=meta)
    assert qsim.apply_control_command(nbl_on) is True
    qsim.world_model.step(1.0)
    assert qsim.world_model.nbl_active is True
    assert qsim.world_model.nbl_allowed is True
    assert qsim.world_model.nbl_power_w > 0.0
