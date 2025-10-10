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

    # Validate detection contents - should have 2 detections (LR and SR)
    assert len(rf.detections) == 2
    
    # Check LR detection (first one - no transponder)
    lr_det = rf.detections[0]
    assert isinstance(lr_det, RadarDetectionModel)
    assert lr_det.range_m >= 0.0
    assert 0.0 <= lr_det.bearing_deg < 360.0
    assert -90.0 <= lr_det.elev_deg <= 90.0
    assert lr_det.snr_db >= 0.0
    assert lr_det.transponder_mode == TransponderModeEnum.OFF
    assert lr_det.transponder_on is False
    assert lr_det.transponder_id is None
    
    # Check SR detection (second one - with transponder)
    sr_det = rf.detections[1]
    assert isinstance(sr_det, RadarDetectionModel)
    assert sr_det.range_m >= 0.0
    assert 0.0 <= sr_det.bearing_deg < 360.0
    assert -90.0 <= sr_det.elev_deg <= 90.0
    assert sr_det.snr_db >= 0.0
    assert sr_det.transponder_mode == TransponderModeEnum.ON
    assert sr_det.transponder_on is True
    assert sr_det.transponder_id is not None


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
    # SR detection is the second one (index 1) which has transponder info
    sr_det = frame.detections[1]

    assert sr_det.transponder_mode == TransponderModeEnum[mode]
    assert sr_det.transponder_on is expected_on
    if expected_id is None:
        assert sr_det.transponder_id is None
    else:
        assert sr_det.transponder_id is not None
        assert sr_det.transponder_id.startswith(expected_id)
