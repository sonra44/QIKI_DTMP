import pytest

from qiki.services.q_sim_service.core.world_model import WorldModel


def test_low_soc_shedding_order_is_stable() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500.0,
            "power_plane": {
                "soc_shed_low_pct": 20.0,
                "soc_shed_high_pct": 30.0,
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "radar_power_w": 40.0,
                "transponder_power_w": 10.0,
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
    assert wm.power_shed_loads == ["radar", "transponder"]
    assert wm.power_shed_reasons == ["low_soc"]

    # Recovery (hysteresis): still shed between low/high.
    wm.battery_level = 25.0
    wm.step(1.0)
    assert wm.power_shed_loads == ["radar", "transponder"]

    # Above high threshold: shedding clears.
    wm.battery_level = 31.0
    wm.step(1.0)
    assert wm.radar_allowed is True
    assert wm.transponder_allowed is True
    assert wm.power_shed_loads == []


def test_thermal_trip_pdu_sheds_radar_transponder_next_tick() -> None:
    # Thermal trip state is computed at the end of the tick, so the power-plane shedding
    # based on that state is observable starting on the next step().
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500.0,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 100.0,
                "radar_power_w": 40.0,
                "transponder_power_w": 10.0,
            },
            "thermal_plane": {
                "enabled": True,
                "ambient_exchange_w_per_c": 0.0,
                "nodes": [
                    {"id": "pdu", "heat_capacity_j_per_c": 10.0, "cooling_w_per_c": 0.0, "t_init_c": 100.0, "t_max_c": 50.0, "t_hysteresis_c": 5.0},
                ],
                "couplings": [],
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
    wm.battery_level = 99.0

    wm.step(1.0)
    assert "THERMAL_TRIP:pdu" in wm.power_faults

    wm.step(1.0)
    assert wm.radar_allowed is False
    assert wm.transponder_allowed is False
    assert "thermal_overheat" in wm.power_shed_reasons
    assert "radar" in wm.power_shed_loads
    assert "transponder" in wm.power_shed_loads


def test_pdu_overcurrent_shedding_order_is_stable_and_recovers() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500.0,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 0.3,  # 8.4W limit
                "base_power_in_w": 0.0,
                "base_power_out_w": 2.0,
                "motion_power_w_per_mps": 40.0,
                "mcqpu_power_w_at_100pct": 0.0,
                "radar_power_w": 4.0,
                "transponder_power_w": 4.0,
                "nbl_active_init": True,
                "nbl_max_power_w": 4.0,
                "nbl_soc_min_pct": 0.0,
                "nbl_core_temp_max_c": 999.0,
            },
        }
    }
    wm = WorldModel(bot_config=bot_config)
    wm.battery_level = 99.0
    wm.temp_core_c = 0.0
    wm.speed = 1.0
    wm.set_runtime_load_inputs(
        radar_enabled=True,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=True,
    )

    wm.step(1.0)
    # PDU enforcement order: nbl -> radar -> transponder.
    assert wm.power_shed_loads[:3] == ["nbl", "radar", "transponder"]
    assert wm.power_shed_reasons == ["pdu_overcurrent"]
    assert wm.power_pdu_throttled is True
    assert "motion" in wm.power_throttled_loads

    # Recovery: remove the load; PDU shedding/throttling must clear automatically next tick.
    wm.speed = 0.0
    wm.nbl_active = False
    wm.set_runtime_load_inputs(
        radar_enabled=False,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=False,
    )
    wm.step(1.0)
    assert wm.power_shed_loads == []
    assert wm.power_shed_reasons == []
    assert wm.power_pdu_throttled is False
    assert "PDU_OVERCURRENT" not in wm.power_faults

