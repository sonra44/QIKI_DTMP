from __future__ import annotations

import json
from pathlib import Path

from qiki.services.q_bios_service.bios_engine import BiosPostInputs, build_bios_status
from qiki.services.q_bios_service.health_checker import SimHealthResult
from qiki.shared.models.core import DeviceStatusEnum


def _write_bot_config(tmp_path: Path, payload: dict) -> str:
    p = tmp_path / "bot_config.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return str(p)


def test_bios_engine_config_missing(tmp_path: Path) -> None:
    status = build_bios_status(
        BiosPostInputs(
            bot_config_path=str(tmp_path / "missing.json"),
            sim_health=SimHealthResult(ok=True, message="ok"),
        )
    )
    assert status.all_systems_go is False
    assert len(status.post_results) == 1
    assert status.post_results[0].status == DeviceStatusEnum.ERROR


def test_bios_engine_devices_ok(tmp_path: Path) -> None:
    cfg_path = _write_bot_config(
        tmp_path,
        {
            "schema_version": "1.0",
            "hardware_profile": {
                "sensors": [{"id": "imu_main", "type": "imu"}],
                "actuators": [{"id": "motor_left", "type": "wheel_motor"}],
            },
            "hardware_manifest": {"mcqpu": {"id": "mcqpu", "type": "mcqpu"}},
        },
    )
    status = build_bios_status(
        BiosPostInputs(
            bot_config_path=cfg_path,
            sim_health=SimHealthResult(ok=True, message="ok"),
        )
    )
    assert status.all_systems_go is True
    assert {d.device_id for d in status.post_results} >= {"imu_main", "motor_left", "mcqpu"}
    assert all(d.status == DeviceStatusEnum.OK for d in status.post_results)


def test_bios_engine_degraded_when_sim_down(tmp_path: Path) -> None:
    cfg_path = _write_bot_config(
        tmp_path,
        {
            "schema_version": "1.0",
            "hardware_profile": {"sensors": [{"id": "imu_main", "type": "imu"}], "actuators": []},
        },
    )
    status = build_bios_status(
        BiosPostInputs(
            bot_config_path=cfg_path,
            sim_health=SimHealthResult(ok=False, message="timeout"),
        )
    )
    assert status.all_systems_go is False
    assert any(d.device_id == "q-sim-service" and d.status == DeviceStatusEnum.ERROR for d in status.post_results)
    assert any(d.device_id == "imu_main" and d.status == DeviceStatusEnum.DEGRADED for d in status.post_results)

