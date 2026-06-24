"""Comms/XPDR virtualization — no-mocks."""

from __future__ import annotations

import json
from dataclasses import fields

from qiki.services.q_sim_service.core.world_model import (
    CommsChannelRecord,
    comms_channels_from_comms_state,
)
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
    assert comms.get("link") in {"online", "offline", "degraded"}
    assert isinstance(comms.get("rssi_dbm"), float)
    assert isinstance(comms.get("snr_db"), float)
    assert isinstance(comms.get("tx_power_w"), float)
    assert isinstance(comms.get("data_rate_kbps"), float)
    assert comms.get("antenna_status") in {"lock", "unlock"}


def test_telemetry_payload_does_not_export_fake_comms_age() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    payload = qsim._build_telemetry_payload(qsim.world_model.get_state())
    comms = payload.get("comms")

    assert isinstance(comms, dict)
    assert "age_s" not in comms
    assert "last_seen_ts" not in comms
    assert comms.get("available") in (True, False, "unknown")
    assert isinstance(comms.get("reason_codes"), (list, tuple))
    assert isinstance(comms.get("reason_text"), str)


def test_sim_xpdr_mode_control_command() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")

    invalid = CommandMessage(command_name="sim.xpdr.mode", parameters={"mode": "MAYBE"}, metadata=meta)
    assert qsim.apply_control_command(invalid) is False

    silent = CommandMessage(command_name="sim.xpdr.mode", parameters={"mode": "SILENT"}, metadata=meta)
    assert qsim.apply_control_command(silent) is True
    payload = qsim._build_telemetry_payload(qsim.world_model.get_state())
    xpdr = (payload.get("comms") or {}).get("xpdr") or {}
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
    id1 = ((p1.get("comms") or {}).get("xpdr") or {}).get("id")
    id2 = ((p2.get("comms") or {}).get("xpdr") or {}).get("id")
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
    comms_payload = payload.get("comms") or {}
    xpdr = (payload.get("comms") or {}).get("xpdr") or {}
    assert comms_payload.get("available") is False
    assert tuple(comms_payload.get("reason_codes") or ()) == ("COMMS_NOT_IMPLEMENTED",)
    assert "not implemented" in str(comms_payload.get("reason_text", "")).lower()
    assert xpdr.get("mode") == "OFF"
    assert xpdr.get("active") is False
    assert xpdr.get("id") is None

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")
    enable = CommandMessage(command_name="sim.xpdr.mode", parameters={"mode": "ON"}, metadata=meta)
    assert qsim.apply_control_command(enable) is False


def test_if_comms_record_exposes_canon_fields() -> None:
    record_fields = {field.name for field in fields(CommsChannelRecord)}

    assert record_fields == {
        "channel_id",
        "channel_class",
        "direction",
        "bandwidth_class",
        "latency",
        "power_cost_W",
        "thermal_node",
        "signature_class",
        "EMCON_state",
        "delivery_state",
        "timestamp",
        "freshness",
        "trust_status",
        "reason_codes",
    }


def test_if_comms_mapper_projects_real_xpdr_channel() -> None:
    qsim = QSimService(QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO"))
    state = qsim.world_model.get_state()
    payload = qsim._build_telemetry_payload(state)

    records = comms_channels_from_comms_state(
        payload.get("comms"),
        power=payload.get("power"),
        thermal=payload.get("thermal"),
        timestamp=payload.get("timestamp"),
    )

    assert len(records) == 1
    xpdr = records[0]
    assert xpdr.channel_id == "transponder"
    assert xpdr.channel_class == "transponder"
    assert xpdr.direction == "tx"
    assert xpdr.latency == payload["comms"]["latency_ms"]
    assert xpdr.power_cost_W == payload["comms"]["tx_power_w"]
    assert xpdr.delivery_state in {"online", "channel_degraded", "power_block", "not_implemented"}
    assert xpdr.EMCON_state == "missing"


def test_if_comms_mapper_marks_missing_comms_not_implemented() -> None:
    records = comms_channels_from_comms_state(None)

    assert len(records) == 1
    record = records[0]
    assert record.channel_id == "missing"
    assert record.delivery_state == "not_implemented"
    assert record.trust_status == "missing"
    assert record.reason_codes == ("COMMS_NOT_IMPLEMENTED",)


def test_if_comms_mapper_surfaces_power_block_without_faking_delivery() -> None:
    records = comms_channels_from_comms_state(
        {
            "enabled": True,
            "available": False,
            "reason_codes": ("COMMS_POWER_BLOCK",),
            "xpdr": {"active": False, "allowed": False, "mode": "ON"},
            "link": "degraded",
            "latency_ms": 1600.0,
            "tx_power_w": 0.0,
            "data_rate_kbps": 0.0,
        },
        power={"shed_loads": ["transponder"], "shed_reasons": ["low_soc"]},
    )

    record = records[0]
    assert record.delivery_state == "power_block"
    assert record.trust_status == "degraded"
    assert "COMMS_POWER_BLOCK" in record.reason_codes


def test_if_comms_mapper_surfaces_thermal_block() -> None:
    records = comms_channels_from_comms_state(
        {
            "enabled": True,
            "available": False,
            "reason_codes": ("COMMS_THERMAL_BLOCK",),
            "xpdr": {"active": True, "allowed": True, "mode": "ON"},
            "link": "online",
            "latency_ms": 80.0,
            "tx_power_w": 5.0,
            "data_rate_kbps": 192.0,
        },
        thermal={"nodes": [{"id": "comms", "temp_c": 80.0, "warn_c": 60.0, "tripped": True}]},
    )

    record = records[0]
    assert record.delivery_state == "thermal_block"
    assert record.trust_status == "degraded"
    assert record.reason_codes == ("COMMS_THERMAL_BLOCK",)


def test_if_comms_mapper_surfaces_emcon_block() -> None:
    records = comms_channels_from_comms_state(
        {
            "enabled": True,
            "available": False,
            "reason_codes": ("EMCON_BLOCK",),
            "xpdr": {"active": True, "allowed": True, "mode": "ON"},
            "link": "online",
            "latency_ms": 80.0,
            "tx_power_w": 5.0,
            "data_rate_kbps": 192.0,
            "EMCON_state": "EMCON_block",
        }
    )

    record = records[0]
    assert record.delivery_state == "EMCON_block"
    assert record.EMCON_state == "EMCON_block"
    assert record.reason_codes == ("EMCON_BLOCK",)


def test_if_comms_mapper_honors_availability_false_reason_codes() -> None:
    records = comms_channels_from_comms_state(
        {
            "enabled": True,
            "available": False,
            "reason_codes": ("COMMS_POWER_BLOCK",),
            "xpdr": {"active": True, "allowed": True, "mode": "ON"},
            "link": "online",
            "latency_ms": 80.0,
            "tx_power_w": 5.0,
            "data_rate_kbps": 192.0,
        }
    )

    record = records[0]
    assert record.delivery_state == "power_block"
    assert record.trust_status == "degraded"
    assert record.reason_codes == ("COMMS_POWER_BLOCK",)


def test_if_comms_mapper_demotes_available_true_with_blocking_reason_codes() -> None:
    records = comms_channels_from_comms_state(
        {
            "enabled": True,
            "available": True,
            "reason_codes": ("COMMS_POWER_BLOCK",),
            "xpdr": {"active": True, "allowed": True, "mode": "ON"},
            "link": "online",
            "latency_ms": 80.0,
            "tx_power_w": 5.0,
            "data_rate_kbps": 192.0,
        }
    )

    record = records[0]
    assert record.delivery_state == "power_block"
    assert record.trust_status == "degraded"
    assert record.reason_codes == ("COMMS_POWER_BLOCK",)


def test_if_comms_mapper_honors_availability_unknown() -> None:
    records = comms_channels_from_comms_state(
        {
            "enabled": True,
            "available": "unknown",
            "reason_codes": ("COMMS_NOT_IMPLEMENTED",),
            "xpdr": {"active": True, "allowed": True, "mode": "ON"},
            "link": "online",
            "latency_ms": 80.0,
            "tx_power_w": 5.0,
            "data_rate_kbps": 192.0,
        }
    )

    record = records[0]
    assert record.delivery_state == "not_implemented"
    assert record.trust_status == "missing"
    assert record.reason_codes == ("COMMS_NOT_IMPLEMENTED",)


def test_if_comms_mapper_treats_missing_availability_as_unknown() -> None:
    records = comms_channels_from_comms_state(
        {
            "enabled": True,
            "xpdr": {"active": True, "allowed": True, "mode": "ON"},
            "link": "online",
            "latency_ms": 80.0,
            "tx_power_w": 5.0,
            "data_rate_kbps": 192.0,
        }
    )

    record = records[0]
    assert record.delivery_state == "not_implemented"
    assert record.trust_status == "missing"
    assert record.reason_codes == ("COMMS_NOT_IMPLEMENTED",)
