from uuid import uuid4

import pytest

try:
    from qiki.shared.models.radar import RadarFrameModel, RadarDetectionModel, RangeBand
    from qiki.services.q_sim_service.radar_publisher import RadarNatsPublisher
except Exception:
    pytest.skip("pydantic not installed; skipping radar tests", allow_module_level=True)


def test_build_headers_uses_frame_id_for_dedup():
    det = RadarDetectionModel(
        range_m=10.0,
        bearing_deg=15.0,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=5.0,
        rcs_dbsm=0.1,
    )
    frame = RadarFrameModel(sensor_id=uuid4(), detections=[det])
    publisher = RadarNatsPublisher("nats://example", sr_threshold_m=5000)
    headers = publisher.build_headers(frame, RangeBand.RR_UNSPECIFIED)

    assert headers["Nats-Msg-Id"] == str(frame.frame_id)
    assert headers["ce_specversion"] == "1.0"
    assert headers["ce_id"] == str(frame.frame_id)
    assert headers["ce_type"] == "qiki.radar.v1.UNSPECIFIEDFrame"
    assert headers["ce_source"] == "urn:qiki:q-sim-service:radar"
    assert headers["ce_datacontenttype"] == "application/json"
    assert headers["ce_time"].endswith("Z")
    assert headers["x-range-band"] == "RR_UNSPECIFIED"
