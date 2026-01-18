from __future__ import annotations

import json
import re
from pathlib import Path

from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config.hardware_profile_hash import compute_hardware_profile_hash
from qiki.shared.config_models import QSimServiceConfig


def test_telemetry_includes_hardware_profile_hash(tmp_path: Path, monkeypatch) -> None:
    bot_config = {
        "hardware_profile": {
            "sensors": [{"id": "imu_main", "type": "imu"}],
            "actuators": [{"id": "rcs_main", "type": "rcs"}],
        },
        "hardware_manifest": {"mcqpu": {"id": "mcqpu", "type": "mcqpu"}},
    }
    cfg_path = tmp_path / "bot_config.json"
    cfg_path.write_text(json.dumps(bot_config), encoding="utf-8")
    monkeypatch.setenv("QIKI_BOT_CONFIG_PATH", str(cfg_path))

    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    payload = qsim._build_telemetry_payload(qsim.world_model.get_state())
    h = payload.get("hardware_profile_hash")

    assert isinstance(h, str)
    assert h == compute_hardware_profile_hash(bot_config)
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", h)

