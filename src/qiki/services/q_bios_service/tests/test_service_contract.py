from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from qiki.services.q_bios_service.config import BiosConfig
from qiki.services.q_bios_service.health_checker import SimHealthResult
from qiki.services.q_bios_service.main import BiosService


def _write_bot_config(path: Path, *, schema_version: str) -> None:
    payload = {
        "schema_version": schema_version,
        "hardware_profile": {
            "sensors": [{"id": "imu_main", "type": "imu"}],
            "actuators": [{"id": "motor_left", "type": "wheel_motor"}],
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_status_payload_contract_and_reload_recomputes_from_current_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_path = tmp_path / "bot_config.json"
    _write_bot_config(cfg_path, schema_version="1.0")

    monkeypatch.setattr(
        "qiki.services.q_bios_service.main.check_qsim_health",
        lambda **_: SimHealthResult(ok=True, message="ok"),
    )

    service = BiosService(
        BiosConfig(
            bot_config_path=str(cfg_path),
            nats_subject="qiki.events.v1.bios_status",
            publish_enabled=False,
        )
    )

    first_payload = service.get_status_payload()
    assert first_payload["event_schema_version"] == 1
    assert first_payload["source"] == "q-bios-service"
    assert first_payload["subject"] == "qiki.events.v1.bios_status"
    assert first_payload["bios_version"] == "1.0"

    _write_bot_config(cfg_path, schema_version="2.0")

    cached_payload = service.get_status_payload()
    assert cached_payload["bios_version"] == "1.0"

    reload_response = service.reload_config()
    assert reload_response == {"ok": True, "reloaded": True}

    reloaded_payload = service.get_status_payload()
    assert reloaded_payload["bios_version"] == "2.0"


def test_publisher_loop_uses_configured_subject_and_status_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_path = tmp_path / "bot_config.json"
    _write_bot_config(cfg_path, schema_version="1.0")

    monkeypatch.setattr(
        "qiki.services.q_bios_service.main.check_qsim_health",
        lambda **_: SimHealthResult(ok=True, message="ok"),
    )

    published: list[tuple[str, dict[str, Any]]] = []
    closed = {"value": False}
    service: BiosService | None = None

    class _FakePublisher:
        def __init__(self, *, nats_url: str) -> None:
            assert nats_url == "nats://example:4222"

        async def publish_json(self, *, subject: str, payload: dict[str, Any]) -> None:
            published.append((subject, payload))
            assert service is not None
            service.stop()

        async def close(self) -> None:
            closed["value"] = True

    monkeypatch.setattr("qiki.services.q_bios_service.main.NatsJsonPublisher", _FakePublisher)

    service = BiosService(
        BiosConfig(
            bot_config_path=str(cfg_path),
            nats_url="nats://example:4222",
            nats_subject="qiki.events.v1.bios_status",
            publish_enabled=True,
            publish_interval_s=0.2,
        )
    )

    asyncio.run(service._publisher_loop())

    assert len(published) == 1
    subject, payload = published[0]
    assert subject == "qiki.events.v1.bios_status"
    assert payload["subject"] == "qiki.events.v1.bios_status"
    assert payload["source"] == "q-bios-service"
    assert payload["event_schema_version"] == 1
    assert closed["value"] is True
