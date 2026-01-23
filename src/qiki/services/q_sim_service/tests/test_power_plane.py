import pytest

from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import Unit as ProtoUnit
from qiki.services.q_sim_service.core.world_model import WorldModel
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.models.telemetry import TelemetrySnapshotModel


def test_power_telemetry_includes_power_plane_fields() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    payload = qsim._build_telemetry_payload(qsim.world_model.get_state())
    normalized = TelemetrySnapshotModel.normalize_payload(payload)

    power = normalized.get("power")
    assert isinstance(power, dict)

    # Supervisor / PDU / supercap fields (no v2, still under power.*).
    assert "shed_reasons" in power
    assert "pdu_limit_w" in power
    assert "pdu_throttled" in power
    assert "throttled_loads" in power
    assert "faults" in power
    assert "supercap_soc_pct" in power
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
    cmd.actuator_id.value = "rcs_port"
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
