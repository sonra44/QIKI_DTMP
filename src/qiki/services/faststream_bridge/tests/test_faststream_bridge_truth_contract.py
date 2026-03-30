from __future__ import annotations

import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest

from qiki.services.faststream_bridge import app as bridge_app
from qiki.shared.models.radar import RadarDetectionModel, RadarFrameModel


class _DummyTrackPublisher:
    def __init__(self, publish_ok: bool = True) -> None:
        self.publish_ok = publish_ok
        self.calls: list[tuple[object, dict[str, str] | None]] = []

    def publish_track(self, track: object, *, extra_headers: dict[str, str] | None = None) -> bool:
        self.calls.append((track, extra_headers))
        return self.publish_ok


def _make_valid_frame() -> RadarFrameModel:
    detection = RadarDetectionModel(
        range_m=100.0,
        bearing_deg=5.0,
        elev_deg=1.0,
        vr_mps=-2.0,
        snr_db=10.0,
        rcs_dbsm=0.5,
        transponder_on=True,
    )
    return RadarFrameModel(sensor_id=uuid4(), detections=[detection])


@pytest.mark.asyncio
async def test_bridge_happy_path_returns_ok_and_event_id(monkeypatch: pytest.MonkeyPatch) -> None:
    publisher = _DummyTrackPublisher(publish_ok=True)
    monkeypatch.setattr(bridge_app, "_track_publisher", publisher)
    monkeypatch.delenv("QIKI_ALLOW_BRIDGE_FALLBACK", raising=False)

    result = await bridge_app.handle_radar_frame(_make_valid_frame(), logging.getLogger("test"))

    assert result.ok is True
    assert result.event_id is not None
    assert result.is_fallback is False
    assert len(publisher.calls) == 1


@pytest.mark.asyncio
async def test_bridge_nodata_input_is_dropped_without_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    publisher = _DummyTrackPublisher(publish_ok=True)
    monkeypatch.setattr(bridge_app, "_track_publisher", publisher)
    monkeypatch.delenv("QIKI_ALLOW_BRIDGE_FALLBACK", raising=False)

    no_data_msg = SimpleNamespace(ok=False, value=None, reason="NO_DATA", is_fallback=False)
    result = await bridge_app.handle_radar_frame(no_data_msg, logging.getLogger("test"))

    assert result.ok is False
    assert result.reason.startswith("DROP:NO_DATA")
    assert result.event_id is None
    assert len(publisher.calls) == 0


@pytest.mark.asyncio
async def test_bridge_invalid_payload_is_rejected_without_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    publisher = _DummyTrackPublisher(publish_ok=True)
    monkeypatch.setattr(bridge_app, "_track_publisher", publisher)

    invalid_payload = {"schema_version": 1, "detections": []}
    result = await bridge_app.handle_radar_frame(invalid_payload, logging.getLogger("test"))

    assert result.ok is False
    assert result.reason.startswith("INVALID_PAYLOAD")
    assert result.event_id is None
    assert len(publisher.calls) == 0


@pytest.mark.asyncio
async def test_bridge_fallback_allowed_publishes_simulated_event(monkeypatch: pytest.MonkeyPatch) -> None:
    publisher = _DummyTrackPublisher(publish_ok=True)
    monkeypatch.setattr(bridge_app, "_track_publisher", publisher)
    monkeypatch.setenv("QIKI_ALLOW_BRIDGE_FALLBACK", "true")

    fallback_msg = SimpleNamespace(ok=False, value=None, reason="NO_DATA", is_fallback=True)
    result = await bridge_app.handle_radar_frame(fallback_msg, logging.getLogger("test"))

    assert result.ok is True
    assert result.is_fallback is True
    assert result.reason == "SIMULATED_EVENT"
    assert result.event_id is not None
    assert len(publisher.calls) == 1
    _track, headers = publisher.calls[0]
    assert headers is not None
    assert headers.get("x-qiki-truth-state") == "NO_DATA"
    assert headers.get("x-qiki-fallback") == "true"
