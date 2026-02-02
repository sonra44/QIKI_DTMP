import json
from pathlib import Path


def test_bot_config_has_battery_capacity_and_init_soc() -> None:
    config_path = Path("src/qiki/services/q_core_agent/config/bot_config.json")
    with config_path.open(encoding="utf-8") as f:
        obj = json.load(f)
    hp = obj.get("hardware_profile", {})
    assert "power_capacity_wh" in hp
    assert "battery_soc_init_pct" in hp
    cap = float(hp["power_capacity_wh"])
    init_soc = float(hp["battery_soc_init_pct"])
    assert cap > 0.0
    assert 0.0 <= init_soc <= 100.0
