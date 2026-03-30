import json
from uuid import uuid4

import pytest

try:
    from qiki.shared.models.radar import RadarFrameModel, RadarDetectionModel
except Exception:
    pytest.skip("pydantic not installed; skipping radar tests", allow_module_level=True)

from qiki.services.q_sim_service.radar_publisher import RadarNatsPublisher


def test_build_payload_json_serializable():
    det = RadarDetectionModel(
        range_m=100.0,
        bearing_deg=10.0,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=15.0,
        rcs_dbsm=1.0,
        transponder_on=False,
    )
    frame = RadarFrameModel(sensor_id=uuid4(), detections=[det])

    data = RadarNatsPublisher.build_payload(frame)
    assert isinstance(data, (bytes, bytearray))

    obj = json.loads(data.decode("utf-8"))
    assert obj["schema_version"] == frame.schema_version
    assert "frame_id" in obj and "sensor_id" in obj
    assert isinstance(obj["detections"], list) and len(obj["detections"]) == 1
    d0 = obj["detections"][0]
    assert d0["range_m"] == pytest.approx(100.0)
    assert 0.0 <= d0["bearing_deg"] < 360.0
