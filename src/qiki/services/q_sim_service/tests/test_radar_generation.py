from uuid import UUID as PyUUID

import pytest

try:
    import pydantic  # noqa: F401
except Exception:
    pytest.skip("pydantic not installed; skipping radar tests", allow_module_level=True)

from qiki.services.q_sim_service.main import QSimService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.radar import (
    RadarFrameModel,
    RadarDetectionModel,
    TransponderModeEnum,
)
from generated.common_types_pb2 import SensorType as ProtoSensorType


@pytest.fixture(autouse=True)
def enable_radar(monkeypatch):
    monkeypatch.setenv("RADAR_ENABLED", "1")
    monkeypatch.delenv("RADAR_TRANSPONDER_MODE", raising=False)
    monkeypatch.delenv("RADAR_TRANSPONDER_ID", raising=False)


def test_generate_radar_frame_basic():
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    sim = QSimService(cfg)

    # Single simulation step should create exactly one radar frame
    sim.step()
    assert len(sim.radar_frames) >= 1

    rf = sim.radar_frames[-1]
    assert isinstance(rf, RadarFrameModel)
    # Validate generated UUIDs
    assert isinstance(rf.frame_id, PyUUID)
    assert isinstance(rf.sensor_id, PyUUID)

    # Validate detection contents
    assert len(rf.detections) == 1
    det = rf.detections[0]
    assert isinstance(det, RadarDetectionModel)

    # Ranges and bounds enforced by validators
    assert det.range_m >= 0.0
    assert 0.0 <= det.bearing_deg < 360.0
    assert -90.0 <= det.elev_deg <= 90.0
    assert det.snr_db >= 0.0
    assert det.transponder_mode == TransponderModeEnum.ON
    assert det.transponder_on is True
    assert det.transponder_id is not None


def test_generate_sensor_data_produces_radar_when_enabled():
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    sim = QSimService(cfg)
    # Принудительно используем только радар в цикле
    sim._sensor_cycle = [int(ProtoSensorType.RADAR)]

    reading = sim.generate_sensor_data()
    assert reading.WhichOneof("sensor_data") == "radar_data"
    assert reading.sensor_type == ProtoSensorType.RADAR
    assert reading.radar_data.detections[0].snr_db >= 0.0


@pytest.mark.parametrize(
    "mode,expected_on,expected_id",
    [
        ("OFF", False, None),
        ("SILENT", False, None),
        ("SPOOF", True, "SPOOF-"),
    ],
)
def test_transponder_modes(monkeypatch, mode, expected_on, expected_id):
    monkeypatch.setenv("RADAR_TRANSPONDER_MODE", mode)
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    sim = QSimService(cfg)

    frame = sim.generate_radar_frame()
    det = frame.detections[0]

    assert det.transponder_mode == TransponderModeEnum[mode]
    assert det.transponder_on is expected_on
    if expected_id is None:
        assert det.transponder_id is None
    else:
        assert det.transponder_id is not None
        assert det.transponder_id.startswith(expected_id)
