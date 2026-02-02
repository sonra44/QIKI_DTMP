"""Comms/XPDR virtualization — no-mocks."""

from __future__ import annotations

import json

from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.core import CommandMessage, MessageMetadata


def test_telemetry_payload_includes_comms_xpdr_block() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    payload = qsim._build_telemetry_payload(qsim.world_model.get_state())
    comms = payload.get("comms")
    assert isinstance(comms, dict)
    assert comms.get("enabled") in (True, False)
    xpdr = comms.get("xpdr")
    assert isinstance(xpdr, dict)
    assert xpdr.get("mode") in {"ON", "OFF", "SILENT", "SPOOF"}
    assert xpdr.get("active") in (True, False)
    assert xpdr.get("allowed") in (True, False)


def test_sim_xpdr_mode_control_command() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")

    invalid = CommandMessage(command_name="sim.xpdr.mode", parameters={"mode": "MAYBE"}, metadata=meta)
    assert qsim.apply_control_command(invalid) is False

    silent = CommandMessage(command_name="sim.xpdr.mode", parameters={"mode": "SILENT"}, metadata=meta)
    assert qsim.apply_control_command(silent) is True
    payload = qsim._build_telemetry_payload(qsim.world_model.get_state())
    xpdr = ((payload.get("comms") or {}).get("xpdr") or {})
    assert xpdr.get("mode") == "SILENT"
    assert xpdr.get("active") is False
    assert xpdr.get("id") is None


def test_xpdr_spoof_id_is_stable_per_session() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")
    spoof = CommandMessage(command_name="sim.xpdr.mode", parameters={"mode": "SPOOF"}, metadata=meta)
    assert qsim.apply_control_command(spoof) is True

    p1 = qsim._build_telemetry_payload(qsim.world_model.get_state())
    p2 = qsim._build_telemetry_payload(qsim.world_model.get_state())
    id1 = (((p1.get("comms") or {}).get("xpdr") or {}).get("id"))
    id2 = (((p2.get("comms") or {}).get("xpdr") or {}).get("id"))
    assert isinstance(id1, str) and id1
    assert id1 == id2


def test_comms_disabled_forces_xpdr_off(monkeypatch, tmp_path) -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")

    base = QSimService(cfg)
    assert isinstance(base._bot_config, dict)
    bot_config = json.loads(json.dumps(base._bot_config))
    hp = bot_config.setdefault("hardware_profile", {})
    comms = hp.setdefault("comms_plane", {})
    comms["enabled"] = False

    path = tmp_path / "bot_config.json"
    path.write_text(json.dumps(bot_config, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setenv("QIKI_BOT_CONFIG_PATH", str(path))
    monkeypatch.delenv("RADAR_TRANSPONDER_MODE", raising=False)

    qsim = QSimService(cfg)

    payload = qsim._build_telemetry_payload(qsim.world_model.get_state())
    xpdr = ((payload.get("comms") or {}).get("xpdr") or {})
    assert xpdr.get("mode") == "OFF"
    assert xpdr.get("active") is False
    assert xpdr.get("id") is None

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")
    enable = CommandMessage(command_name="sim.xpdr.mode", parameters={"mode": "ON"}, metadata=meta)
    assert qsim.apply_control_command(enable) is False
