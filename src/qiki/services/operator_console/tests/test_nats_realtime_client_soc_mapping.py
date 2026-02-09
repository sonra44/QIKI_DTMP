import json
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from qiki.services.operator_console.clients.nats_realtime_client import RealtimeNATSClient


@pytest.mark.asyncio
async def test_subscribe_system_telemetry_prefers_canonical_power_soc_pct() -> None:
    client = RealtimeNATSClient("nats://test:4222")
    captured: Dict[str, Any] = {}
    seen: list[dict] = []

    async def fake_subscribe(subject: str, cb):  # type: ignore[no-untyped-def]
        captured["subject"] = subject
        captured["cb"] = cb
        return object()

    client.nc = SimpleNamespace(subscribe=fake_subscribe)
    client.register_callback("telemetry", seen.append)

    await client.subscribe_system_telemetry()
    assert "cb" in captured

    msg = SimpleNamespace(
        data=json.dumps(
            {
                "position": {"x": 1.0, "y": 2.0, "z": 3.0},
                "velocity": 4.0,
                "heading": 5.0,
                "battery": 99.0,  # legacy alias must not win over canonical source
                "power": {"soc_pct": 12.5},
            }
        ).encode("utf-8")
    )
    await captured["cb"](msg)

    telemetry = client.latest_data["telemetry"]
    assert telemetry["soc_pct"] == 12.5
    assert telemetry["battery"] == 12.5
    assert seen
    assert seen[-1]["soc_pct"] == 12.5


@pytest.mark.asyncio
async def test_subscribe_system_telemetry_fallbacks_to_legacy_battery_when_soc_missing() -> None:
    client = RealtimeNATSClient("nats://test:4222")
    captured: Dict[str, Any] = {}

    async def fake_subscribe(subject: str, cb):  # type: ignore[no-untyped-def]
        captured["cb"] = cb
        return object()

    client.nc = SimpleNamespace(subscribe=fake_subscribe)
    await client.subscribe_system_telemetry()

    msg = SimpleNamespace(
        data=json.dumps(
            {
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "velocity": 0.0,
                "heading": 0.0,
                "battery": 47.0,
            }
        ).encode("utf-8")
    )
    await captured["cb"](msg)

    telemetry = client.latest_data["telemetry"]
    assert telemetry["soc_pct"] == 47.0
    assert telemetry["battery"] == 47.0
