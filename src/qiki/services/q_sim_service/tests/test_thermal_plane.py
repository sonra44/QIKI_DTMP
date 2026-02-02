from qiki.services.q_sim_service.core.world_model import WorldModel


def test_thermal_nodes_follow_config_and_no_fake_defaults() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": 0.0,
                "base_power_out_w": 0.0,
                "motion_power_w_per_mps": 0.0,
                "mcqpu_power_w_at_100pct": 0.0,
                "radar_power_w": 0.0,
                "transponder_power_w": 0.0,
                "nbl_active_init": False,
                "nbl_max_power_w": 0.0,
                "nbl_soc_min_pct": 0.0,
                "nbl_core_temp_max_c": 90.0,
            },
            "thermal_plane": {
                "enabled": True,
                "ambient_exchange_w_per_c": 0.0,
                "nodes": [
                    {
                        "id": "core",
                        "heat_capacity_j_per_c": 1000.0,
                        "cooling_w_per_c": 1.0,
                        "t_init_c": 25.0,
                        "t_max_c": 90.0,
                        "t_hysteresis_c": 5.0,
                    },
                    {
                        "id": "pdu",
                        "heat_capacity_j_per_c": 800.0,
                        "cooling_w_per_c": 0.5,
                        "t_init_c": 20.0,
                        "t_max_c": 95.0,
                        "t_hysteresis_c": 5.0,
                    },
                ],
                "couplings": [{"a": "core", "b": "pdu", "k_w_per_c": 0.2}],
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

    thermal = wm.get_state().get("thermal", {})
    nodes = thermal.get("nodes", [])
    assert isinstance(nodes, list)
    assert [n.get("id") for n in nodes] == ["core", "pdu"]
    assert all("temp_c" in n for n in nodes)
    assert all("tripped" in n for n in nodes)
    assert all("trip_c" in n for n in nodes)
    assert all("hys_c" in n for n in nodes)


def test_thermal_plane_cools_towards_ambient_when_no_heat_sources() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": 0.0,
                "base_power_out_w": 0.0,
                "motion_power_w_per_mps": 0.0,
                "mcqpu_power_w_at_100pct": 0.0,
                "radar_power_w": 0.0,
                "transponder_power_w": 0.0,
                "nbl_active_init": False,
                "nbl_max_power_w": 0.0,
                "nbl_soc_min_pct": 0.0,
                "nbl_core_temp_max_c": 90.0,
            },
            "thermal_plane": {
                "enabled": True,
                "ambient_exchange_w_per_c": 0.0,
                "nodes": [
                    {
                        "id": "core",
                        "heat_capacity_j_per_c": 1000.0,
                        "cooling_w_per_c": 2.0,
                        "t_init_c": 40.0,
                        "t_max_c": 90.0,
                        "t_hysteresis_c": 5.0,
                    }
                ],
                "couplings": [],
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
    # Ambient is -60 C by default.
    before = float(wm.get_state()["thermal"]["nodes"][0]["temp_c"])
    wm.step(1.0)
    mid = float(wm.get_state()["thermal"]["nodes"][0]["temp_c"])
    wm.step(1.0)
    after = float(wm.get_state()["thermal"]["nodes"][0]["temp_c"])
    assert mid < before
    assert after < mid


def test_core_overheat_sets_fault_and_blocks_nbl() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": 200.0,
                "base_power_out_w": 0.0,
                "motion_power_w_per_mps": 0.0,
                "mcqpu_power_w_at_100pct": 0.0,
                "radar_power_w": 0.0,
                "transponder_power_w": 0.0,
                "nbl_active_init": True,
                "nbl_max_power_w": 20.0,
                "nbl_soc_min_pct": 10.0,
                "nbl_core_temp_max_c": 90.0,
            },
            "thermal_plane": {
                "enabled": True,
                "ambient_exchange_w_per_c": 0.0,
                "nodes": [
                    {
                        "id": "core",
                        "heat_capacity_j_per_c": 1000.0,
                        "cooling_w_per_c": 0.0,
                        "t_init_c": 100.0,
                        "t_max_c": 90.0,
                        "t_hysteresis_c": 5.0,
                    }
                ],
                "couplings": [],
            },
        }
    }

    wm = WorldModel(bot_config=bot_config)
    wm.battery_level = 99.0
    wm.temp_core_c = 100.0
    wm.set_runtime_load_inputs(
        radar_enabled=False,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=False,
    )
    wm.step(1.0)

    state = wm.get_state()
    power = state.get("power", {})
    assert power.get("nbl_active") is True
    assert power.get("nbl_allowed") is False
    assert float(power.get("nbl_power_w", 0.0)) == 0.0
    faults = power.get("faults", [])
    assert isinstance(faults, list)
    assert "THERMAL_TRIP:core" in faults

    thermal = state.get("thermal", {})
    nodes = thermal.get("nodes", [])
    assert isinstance(nodes, list)
    core = next((n for n in nodes if isinstance(n, dict) and n.get("id") == "core"), None)
    assert isinstance(core, dict)
    assert core.get("tripped") is True
    assert float(core.get("trip_c", 0.0)) == 90.0
    assert float(core.get("hys_c", 0.0)) == 5.0


def test_thermal_trip_hysteresis_clears_when_below_trip_minus_hys() -> None:
    bot_config = {
        "hardware_profile": {
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 28.0,
                "max_bus_a": 10.0,
                "base_power_in_w": 0.0,
                "base_power_out_w": 0.0,
                "motion_power_w_per_mps": 0.0,
                "mcqpu_power_w_at_100pct": 0.0,
                "radar_power_w": 0.0,
                "transponder_power_w": 0.0,
                "nbl_active_init": False,
                "nbl_max_power_w": 0.0,
                "nbl_soc_min_pct": 0.0,
                "nbl_core_temp_max_c": 90.0,
            },
            "thermal_plane": {
                "enabled": True,
                "ambient_exchange_w_per_c": 0.0,
                "nodes": [
                    {
                        "id": "core",
                        "heat_capacity_j_per_c": 1000.0,
                        "cooling_w_per_c": 0.0,
                        "t_init_c": 100.0,
                        "t_max_c": 90.0,
                        "t_hysteresis_c": 5.0,
                    }
                ],
                "couplings": [],
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
    state = wm.get_state()
    power = state.get("power", {})
    faults = power.get("faults", [])
    assert isinstance(faults, list)
    assert "THERMAL_TRIP:core" in faults
    thermal = state.get("thermal", {})
    nodes = thermal.get("nodes", [])
    assert isinstance(nodes, list)
    core = next((n for n in nodes if isinstance(n, dict) and n.get("id") == "core"), None)
    assert isinstance(core, dict)
    assert core.get("tripped") is True

    # Force the node below (trip - hysteresis) and ensure trip clears next step.
    wm._thermal_nodes["core"]["temp_c"] = 80.0
    wm.step(1.0)
    state2 = wm.get_state()
    power2 = state2.get("power", {})
    faults2 = power2.get("faults", [])
    assert isinstance(faults2, list)
    assert "THERMAL_TRIP:core" not in faults2
    core2 = next(
        (
            n
            for n in state2.get("thermal", {}).get("nodes", [])
            if isinstance(n, dict) and n.get("id") == "core"
        ),
        None,
    )
    assert isinstance(core2, dict)
    assert core2.get("tripped") is False
