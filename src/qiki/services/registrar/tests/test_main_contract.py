from __future__ import annotations

import asyncio
from typing import Any

from qiki.services.registrar import main as registrar_main


class _DummyLogger:
    def info(self, *args: Any, **kwargs: Any) -> None:
        return

    def warning(self, *args: Any, **kwargs: Any) -> None:
        return


def test_handle_radar_frame_fan_in_and_audit_fan_out(monkeypatch) -> None:  # noqa: ANN001
    sensor_calls: list[tuple[str, str, dict[str, Any]]] = []
    published: list[dict[str, Any]] = []

    class _FakeRegistrarService:
        def register_sensor_event(self, sensor_id: str, status: str, details: dict[str, Any]) -> None:
            sensor_calls.append((sensor_id, status, details))

    async def _fake_publish(record: dict[str, Any], logger: Any) -> None:
        published.append(record)

    monkeypatch.setattr(registrar_main, "registrar_service", _FakeRegistrarService())
    monkeypatch.setattr(registrar_main, "_publish_audit", _fake_publish)

    msg = {
        "frame_id": "frame-123",
        "sensor_id": "radar_01",
        "detections": [{"track_id": "t-1"}, {"track_id": "t-2"}],
    }

    asyncio.run(registrar_main.handle_radar_frame(msg, _DummyLogger()))

    assert sensor_calls == [
        (
            "radar_01",
            "ACTIVE",
            {
                "event_code": registrar_main.RegistrarCode.RADAR_FRAME_RECEIVED,
                "frame_id": "frame-123",
                "detections_count": 2,
                "description": "Radar frame processed",
            },
        )
    ]
    assert len(published) == 1
    assert published[0]["event_type"] == "RADAR_FRAME_RECEIVED"
    assert published[0]["source"] == "registrar"
    assert published[0]["payload"] == {
        "frame_id": "frame-123",
        "sensor_id": "radar_01",
        "detections_count": 2,
    }


def test_handle_system_events_skips_registrar_self_generated_audit(monkeypatch) -> None:  # noqa: ANN001
    register_calls: list[tuple[str, str, dict[str, Any]]] = []
    published: list[dict[str, Any]] = []

    class _FakeRegistrarService:
        def register_system_event(self, source: str, severity: str, details: dict[str, Any]) -> None:
            register_calls.append((source, severity, details))

    async def _fake_publish(record: dict[str, Any], logger: Any) -> None:
        published.append(record)

    monkeypatch.setattr(registrar_main, "registrar_service", _FakeRegistrarService())
    monkeypatch.setattr(registrar_main, "_publish_audit", _fake_publish)

    msg = {
        "source": "registrar",
        "event_type": "SYSTEM_EVENT",
        "payload": {"wrapped": True},
    }

    asyncio.run(registrar_main.handle_system_events(msg, _DummyLogger()))

    assert register_calls == []
    assert published == []
