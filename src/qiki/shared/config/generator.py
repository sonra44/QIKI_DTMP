"""Configuration generator from BotSpec."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List

from qiki.shared.models.bot_spec import load_bot_spec


def generate_bot_config_from_spec(spec_path: str | Path | None = None) -> Dict[str, Any]:
    """Generate bot configuration from BotSpec."""
    spec = load_bot_spec(spec_path)
    profile = spec.to_runtime_profile()
    
    # Convert to configuration format
    config: Dict[str, Any] = {
        "schema_version": "1.0",
        "bot_id": spec.metadata.id,
        "bot_type": "configured_bot",
        "mode": "full",
        "hardware_profile": {
            "max_speed_mps": 1.0,
            "power_capacity_wh": 500,
            "power_plane": {
                "bus_v_nominal": 28.0,
                "bus_v_min": 22.0,
                "max_bus_a": 5.0,
                "base_power_in_w": 30.0,
                "base_power_out_w": 60.0,
                "motion_power_w_per_mps": 40.0,
                "mcqpu_power_w_at_100pct": 35.0,
                "radar_power_w": 18.0,
                "transponder_power_w": 6.0,
                "soc_shed_low_pct": 20.0,
                "soc_shed_high_pct": 30.0,
                "supercap_capacity_wh": 5.0,
                "supercap_soc_pct_init": 70.0,
                "supercap_max_charge_w": 120.0,
                "supercap_max_discharge_w": 200.0,
                "dock_connected_init": False,
                "dock_station_bus_v": 28.0,
                "dock_station_max_power_w": 250.0,
                "dock_current_limit_a": 10.0,
                "dock_soft_start_s": 2.0,
                "dock_temp_c_init": -60.0,
                "nbl_active_init": False,
                "nbl_max_power_w": 120.0,
                "nbl_soc_min_pct": 35.0,
                "nbl_core_temp_max_c": 90.0,
            },
            "thermal_plane": {
                "enabled": True,
                "ambient_exchange_w_per_c": 0.2,
                "nodes": [
                    {
                        "id": "core",
                        "heat_capacity_j_per_c": 800.0,
                        "cooling_w_per_c": 1.2,
                        "t_init_c": 25.0,
                        "t_max_c": 90.0,
                        "t_hysteresis_c": 5.0,
                    },
                    {
                        "id": "pdu",
                        "heat_capacity_j_per_c": 650.0,
                        "cooling_w_per_c": 0.9,
                        "t_init_c": 25.0,
                        "t_max_c": 95.0,
                        "t_hysteresis_c": 5.0,
                    },
                    {
                        "id": "supercap",
                        "heat_capacity_j_per_c": 400.0,
                        "cooling_w_per_c": 0.7,
                        "t_init_c": 20.0,
                        "t_max_c": 85.0,
                        "t_hysteresis_c": 5.0,
                    },
                    {
                        "id": "battery",
                        "heat_capacity_j_per_c": 1200.0,
                        "cooling_w_per_c": 0.3,
                        "t_init_c": 20.0,
                        "t_max_c": 70.0,
                        "t_hysteresis_c": 3.0,
                    },
                    {
                        "id": "dock_bridge",
                        "heat_capacity_j_per_c": 500.0,
                        "cooling_w_per_c": 0.9,
                        "t_init_c": -60.0,
                        "t_max_c": 120.0,
                        "t_hysteresis_c": 5.0,
                    },
                    {
                        "id": "hull",
                        "heat_capacity_j_per_c": 3000.0,
                        "cooling_w_per_c": 1.5,
                        "t_init_c": -50.0,
                        "t_max_c": 140.0,
                        "t_hysteresis_c": 10.0,
                    },
                ],
                "couplings": [
                    {"a": "core", "b": "pdu", "k_w_per_c": 0.4},
                    {"a": "pdu", "b": "supercap", "k_w_per_c": 0.3},
                    {"a": "pdu", "b": "battery", "k_w_per_c": 0.15},
                    {"a": "dock_bridge", "b": "hull", "k_w_per_c": 0.4},
                    {"a": "core", "b": "hull", "k_w_per_c": 0.2},
                ],
            },
            "propulsion_plane": {
                "enabled": True,
                "thrusters_path": "config/propulsion/thrusters.json",
                "propellant_kg_init": 12.0,
                "isp_s": 60.0,
                "rcs_power_w_at_100pct": 80.0,
                "heat_fraction_to_hull": 0.35,
                "pulse_window_s": 0.25,
                "ztt_torque_tol_nm": 25.0,
            },
            "docking_plane": {
                "enabled": True,
                "ports": ["A", "B"],
                "default_port": "A",
            },
            "sensor_plane": {
                "enabled": True,
                "imu": {"enabled": True},
                "radiation": {"enabled": True},
                "proximity": {"enabled": False},
                "solar": {"enabled": False},
                "star_tracker": {"enabled": False},
                "magnetometer": {"enabled": False},
            },
            "actuators": [],
            "sensors": []
        },
        "runtime_profile": profile
    }
    
    # Map components to actuators/sensors based on provides
    actuators: List[Dict[str, str]] = []
    sensors: List[Dict[str, str]] = []
    
    for name, component in spec.components.items():
        # Map common component types to actuators/sensors
        if "motion_command" in component.provides:
            actuators.append({"id": name, "type": component.type})
        elif "sensor_frame" in component.provides:
            sensors.append({"id": name, "type": component.type})
        elif "dc_out" in component.provides:
            actuators.append({"id": name, "type": component.type})
        elif "energy_status" in component.provides:
            sensors.append({"id": name, "type": component.type})
    
    config["hardware_profile"]["actuators"] = actuators
    config["hardware_profile"]["sensors"] = sensors
    
    return config


def save_bot_config(config: Dict[str, Any], output_path: str | Path) -> None:
    """Save bot configuration to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
