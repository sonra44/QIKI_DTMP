from __future__ import annotations

import asyncio

import pytest
from google.protobuf.timestamp_pb2 import Timestamp

from generated.common_types_pb2 import SensorType as ProtoSensorType
from generated.common_types_pb2 import UUID, Unit as ProtoUnit
from generated.sensor_raw_in_pb2 import SensorReading
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig


def _cfg() -> QSimServiceConfig:
    return QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")


def _sensor_reading(value: float) -> SensorReading:
    ts = Timestamp()
    ts.GetCurrentTime()
    return SensorReading(
        sensor_id=UUID(value=f"sensor-{int(value)}"),
        sensor_type=int(ProtoSensorType.LIDAR),
        timestamp=ts,
        scalar_data=value,
        unit=ProtoUnit.METERS,
        is_valid=True,
    )


def test_sensor_queue_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QSIM_SENSOR_QUEUE_MAX", "100")
    sim = QSimService(_cfg())
    for _ in range(1000):
        sim.step(publish_radar=False)
    assert len(sim.sensor_data_queue) == 1


def test_radar_frames_queue_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_ENABLED", "1")
    monkeypatch.setenv("QSIM_RADAR_FRAMES_MAX", "80")
    sim = QSimService(_cfg())
    for _ in range(1000):
        sim.step()
    assert len(sim.radar_frames) == 80


@pytest.mark.asyncio
async def test_sensor_queue_returns_latest_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QSIM_SENSOR_QUEUE_MAX", "10")
    sim = QSimService(_cfg())

    first = _sensor_reading(1.0)
    second = _sensor_reading(2.0)
    sim._append_sensor_data(first)
    sim._append_sensor_data(second)

    got_latest = await asyncio.wait_for(sim.get_sensor_data(), timeout=1.0)
    assert got_latest.scalar_data == 2.0
    assert len(sim.sensor_data_queue) == 0


def test_overflow_does_not_crash_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QSIM_SENSOR_QUEUE_MAX", "3")
    monkeypatch.setenv("QSIM_RADAR_FRAMES_MAX", "3")
    monkeypatch.setenv("RADAR_ENABLED", "1")
    sim = QSimService(_cfg())

    for _ in range(100):
        sim.step()

    assert len(sim.sensor_data_queue) == 1
    assert len(sim.radar_frames) == 3


def test_invalid_queue_env_falls_back_to_defaults(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("QSIM_SENSOR_QUEUE_MAX", "oops")
    monkeypatch.setenv("QSIM_RADAR_FRAMES_MAX", "-10")
    sim = QSimService(_cfg())

    assert sim.sensor_data_queue.maxlen == 256
    assert sim.radar_frames.maxlen == 256
    assert "QSIM_SENSOR_QUEUE_MAX invalid='oops', fallback to default=256" in caplog.text
    assert "QSIM_RADAR_FRAMES_MAX invalid='-10', fallback to default=256" in caplog.text
