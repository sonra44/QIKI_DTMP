from dataclasses import fields

from qiki.services.q_sim_service.core.world_model import (
    ThermalTelemetryRecord,
    WorldModel,
    thermal_telemetry_from_thermal_state,
)


import pytest


def test_if_thermal_telem_record_exposes_canon_fields() -> None:
    record_fields = {field.name for field in fields(ThermalTelemetryRecord)}

    assert {
        "thermal_node_id",
        "temp_current",
        "thermal_state",
        "temp_warning",
        "temp_critical",
        "heat_active_W",
        "cooldown_state",
        "blocked_commands",
        "timestamp",
        "freshness",
        "source",
        "trust_status",
        "reason_codes",
    } <= record_fields


def test_if_thermal_telem_mapper_keeps_nodes_separate() -> None:
    records = thermal_telemetry_from_thermal_state(
        {
            "nodes": [
                {
                    "id": "core",
                    "temp_c": 82.0,
                    "warned": True,
                    "tripped": False,
                    "warn_c": 80.0,
                    "trip_c": 90.0,
                },
                {
                    "id": "pdu",
                    "temp_c": 96.0,
                    "warned": False,
                    "tripped": True,
                    "warn_c": 85.0,
                    "trip_c": 95.0,
                },
            ]
        },
        timestamp=123.0,
        freshness="fresh",
    )

    assert [record.thermal_node_id for record in records] == ["core", "pdu"]
    core, pdu = records
    assert core.temp_current == pytest.approx(82.0)
    assert core.thermal_state == "hot"
    assert core.temp_warning == pytest.approx(80.0)
    assert core.temp_critical == pytest.approx(90.0)
    assert core.heat_active_W is None
    assert core.cooldown_state == "missing"
    assert core.blocked_commands == ()
    assert core.trust_status == "trusted"
    assert core.reason_codes == ("THERMAL_NODE_HOT",)
    assert core.timestamp == pytest.approx(123.0)

    assert pdu.temp_current == pytest.approx(96.0)
    assert pdu.thermal_state == "critical"
    assert pdu.blocked_commands == ("radar", "transponder", "nbl")
    assert pdu.trust_status == "trusted"
    assert pdu.reason_codes == ("THERMAL_NODE_CRITICAL", "PDU_THERMAL_BLOCK")


def test_if_thermal_telem_mapper_marks_missing_nodes_unknown() -> None:
    records = thermal_telemetry_from_thermal_state({}, freshness="unknown")

    assert len(records) == 1
    record = records[0]
    assert record.thermal_node_id == "missing"
    assert record.temp_current is None
    assert record.thermal_state == "unknown"
    assert record.temp_warning is None
    assert record.temp_critical is None
    assert record.heat_active_W is None
    assert record.cooldown_state == "missing"
    assert record.blocked_commands == ()
    assert record.freshness == "unknown"
    assert record.trust_status == "missing"
    assert record.reason_codes == ("THERMAL_TELEM_MISSING",)


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
    assert all("warned" in n for n in nodes)
    assert all("warn_c" in n for n in nodes)
    assert all("trip_c" in n for n in nodes)
    assert all("hys_c" in n for n in nodes)

    core = next((n for n in nodes if isinstance(n, dict) and n.get("id") == "core"), None)
    assert isinstance(core, dict)
    assert float(core.get("warn_c", 0.0)) == pytest.approx(80.0)
    assert core.get("warned") is False

    pdu = next((n for n in nodes if isinstance(n, dict) and n.get("id") == "pdu"), None)
    assert isinstance(pdu, dict)
    assert float(pdu.get("warn_c", 0.0)) == pytest.approx(85.0)
    assert pdu.get("warned") is False

    records = thermal_telemetry_from_thermal_state(thermal, timestamp=wm.sim_time_epoch_ts())
    assert [record.thermal_node_id for record in records] == ["core", "pdu"]
    assert records[0].temp_current == pytest.approx(float(core["temp_c"]))
    assert records[1].temp_warning == pytest.approx(85.0)


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
        (n for n in state2.get("thermal", {}).get("nodes", []) if isinstance(n, dict) and n.get("id") == "core"),
        None,
    )
    assert isinstance(core2, dict)
    assert core2.get("tripped") is False


def test_thermal_warn_sets_warned_before_trip() -> None:
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
                        "t_init_c": 85.0,
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
    core = next(
        (
            n
            for n in wm.get_state().get("thermal", {}).get("nodes", [])
            if isinstance(n, dict) and n.get("id") == "core"
        ),
        None,
    )
    assert isinstance(core, dict)
    assert float(core.get("warn_c", 0.0)) == pytest.approx(80.0)
    assert core.get("warned") is True
    assert core.get("tripped") is False


def test_thermal_warn_uses_explicit_t_warn_override() -> None:
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
                        "t_init_c": 88.0,
                        "t_warn_c": 88.0,
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
    core = next(
        (
            n
            for n in wm.get_state().get("thermal", {}).get("nodes", [])
            if isinstance(n, dict) and n.get("id") == "core"
        ),
        None,
    )
    assert isinstance(core, dict)
    assert float(core.get("warn_c", 0.0)) == pytest.approx(88.0)
    assert core.get("warned") is True
    assert core.get("tripped") is False


def test_thermal_trip_boundary_is_stable_with_hysteresis() -> None:
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
    assert "THERMAL_TRIP:core" in wm.get_state().get("power", {}).get("faults", [])

    # Inclusive clear threshold: trip clears at temp <= (trip - hys) and remains clear without flap.
    wm._thermal_nodes["core"]["temp_c"] = 85.0
    wm.step(1.0)
    assert "THERMAL_TRIP:core" not in wm.get_state().get("power", {}).get("faults", [])
    wm._thermal_nodes["core"]["temp_c"] = 85.0
    wm.step(1.0)
    assert "THERMAL_TRIP:core" not in wm.get_state().get("power", {}).get("faults", [])

    wm._thermal_nodes["core"]["temp_c"] = 90.0
    wm.step(1.0)
    assert "THERMAL_TRIP:core" in wm.get_state().get("power", {}).get("faults", [])


def test_thermal_step_does_not_overshoot_below_ambient_from_above() -> None:
    # Ambient is -60C by default; with a large dt and strong cooling, Euler integration may overshoot.
    # We clamp only overshoot from above ambient (passive cooling cannot drive below ambient).
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
                        "heat_capacity_j_per_c": 1.0,
                        "cooling_w_per_c": 2000.0,
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
    wm.step(10.0)
    core = next(
        (
            n
            for n in wm.get_state().get("thermal", {}).get("nodes", [])
            if isinstance(n, dict) and n.get("id") == "core"
        ),
        None,
    )
    assert isinstance(core, dict)
    assert float(core.get("temp_c", 0.0)) == pytest.approx(-60.0)


def test_thermal_allows_node_to_remain_below_ambient_without_clamp_up() -> None:
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
                        "t_init_c": -100.0,
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
    before = float(wm.get_state()["thermal"]["nodes"][0]["temp_c"])
    wm.step(1.0)
    after = float(wm.get_state()["thermal"]["nodes"][0]["temp_c"])

    assert before < -60.0
    assert after > before
    assert after < -60.0


def test_thermal_config_warns_and_persists_when_hysteresis_is_zero() -> None:
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
                        "t_init_c": 25.0,
                        "t_max_c": 90.0,
                        "t_hysteresis_c": 0.0,
                    }
                ],
                "couplings": [],
            },
        }
    }

    wm = WorldModel(bot_config=bot_config)
    assert "THERMAL_PLANE_PARAM_INVALID:core:hys_zero" in wm.power_faults
    assert float(wm._thermal_nodes["core"]["hys_c"]) == pytest.approx(0.0)

    wm.set_runtime_load_inputs(
        radar_enabled=False,
        sensor_queue_depth=0,
        actuator_queue_depth=0,
        transponder_active=False,
    )
    wm.step(1.0)

    faults = wm.get_state().get("power", {}).get("faults", [])
    assert isinstance(faults, list)
    assert "THERMAL_PLANE_PARAM_INVALID:core:hys_zero" in faults
