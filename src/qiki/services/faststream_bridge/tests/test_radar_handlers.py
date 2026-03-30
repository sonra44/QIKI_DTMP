from uuid import uuid4

import pytest

from qiki.services.faststream_bridge.radar_handlers import (
    frame_to_track,
    reset_track_store,
)
from qiki.shared.models.radar import (
    RadarDetectionModel,
    RadarFrameModel,
    RadarTrackModel,
    RadarTrackStatusEnum,
    TransponderModeEnum,
)


def _make_detection(**overrides):
    defaults = dict(
        range_m=120.0,
        bearing_deg=10.0,
        elev_deg=3.0,
        vr_mps=-5.0,
        snr_db=14.0,
        rcs_dbsm=1.2,
        transponder_on=True,
        transponder_mode=TransponderModeEnum.ON,
        transponder_id="ALLY-001",
    )
    defaults.update(overrides)
    return RadarDetectionModel(**defaults)


def test_frame_to_track_basic_mapping():
    reset_track_store()
    detection = _make_detection()
    frame = RadarFrameModel(sensor_id=uuid4(), detections=[detection])

    track = frame_to_track(frame)

    assert isinstance(track, RadarTrackModel)
    assert pytest.approx(track.range_m, rel=1e-6) == detection.range_m
    assert pytest.approx(track.bearing_deg, rel=1e-6) == detection.bearing_deg
    assert track.transponder_on is True
    assert track.quality > 0.0
    assert track.transponder_mode == TransponderModeEnum.ON
    assert track.transponder_id == "ALLY-001"


def test_frame_to_track_empty_frame_produces_defaults():
    reset_track_store()
    frame = RadarFrameModel(sensor_id=uuid4(), detections=[])

    track = frame_to_track(frame)

    assert isinstance(track, RadarTrackModel)
    assert track.range_m == 0.0
    assert track.snr_db == 0.0
    assert track.status == RadarTrackStatusEnum.LOST
    assert track.transponder_mode == TransponderModeEnum.OFF
    assert track.transponder_id is None


def test_frame_to_track_stateful_tracking_merges_detections():
    reset_track_store()
    first = _make_detection(range_m=100.0, bearing_deg=1.0, vr_mps=0.1, snr_db=16.0)
    second = _make_detection(
        range_m=101.0,
        bearing_deg=1.5,
        vr_mps=0.2,
        snr_db=18.0,
        transponder_on=False,
        transponder_mode=TransponderModeEnum.SILENT,
        transponder_id=None,
    )

    frame = RadarFrameModel(sensor_id=uuid4(), detections=[first])
    initial_track = frame_to_track(frame)

    follow_up = RadarFrameModel(sensor_id=frame.sensor_id, detections=[second])
    updated_track = frame_to_track(follow_up)

    assert initial_track.track_id == updated_track.track_id
    assert updated_track.status in {
        RadarTrackStatusEnum.NEW,
        RadarTrackStatusEnum.TRACKED,
    }
    assert pytest.approx(updated_track.range_m, rel=1e-2) == second.range_m
    assert abs(updated_track.bearing_deg - second.bearing_deg) < 0.5
    assert updated_track.transponder_on is False
    assert updated_track.transponder_mode == TransponderModeEnum.SILENT
    assert updated_track.transponder_id is None
