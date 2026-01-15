import pytest

from qiki.services.q_sim_service.core.world_model import WorldModel
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
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
