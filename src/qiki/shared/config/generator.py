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
