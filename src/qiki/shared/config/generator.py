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