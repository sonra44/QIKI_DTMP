from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from qiki.services.faststream_bridge.radar_track_store import RadarTrackStore
from qiki.shared.models.radar import (
    RadarDetectionModel,
    RadarFrameModel,
    RadarTrackStatusEnum,
    TransponderModeEnum,
)


def _frame_with_detection(
    *,
    range_m: float,
    bearing_deg: float,
    elev_deg: float,
    vr_mps: float,
    snr_db: float,
    timestamp: datetime,
):
    detection = RadarDetectionModel(
        range_m=range_m,
        bearing_deg=bearing_deg,
        elev_deg=elev_deg,
        vr_mps=vr_mps,
        snr_db=snr_db,
        rcs_dbsm=1.0,
        transponder_on=False,
        transponder_mode=TransponderModeEnum.OFF,
        transponder_id=None,
    )
    return RadarFrameModel(
        sensor_id=uuid4(),
        timestamp=timestamp,
        detections=[detection],
    )


def test_track_store_creates_and_updates_track():
    store = RadarTrackStore()
    start = datetime.now(UTC)
    first = _frame_with_detection(
        range_m=50.0,
        bearing_deg=5.0,
        elev_deg=0.0,
        vr_mps=0.5,
        snr_db=12.0,
        timestamp=start,
    )
    tracks = store.process_frame(first)
    assert len(tracks) == 1
    initial_track = tracks[0]
    assert initial_track.ts_event == start
    assert initial_track.ts_ingest is not None
    assert pytest.approx(initial_track.range_m, rel=1e-3) == 50.0
    assert initial_track.status in {
        RadarTrackStatusEnum.NEW,
        RadarTrackStatusEnum.TRACKED,
    }

    later = _frame_with_detection(
        range_m=51.0,
        bearing_deg=5.5,
        elev_deg=0.1,
        vr_mps=0.6,
        snr_db=14.0,
        timestamp=start + timedelta(milliseconds=200),
    )
    tracks = store.process_frame(later)
    assert len(tracks) == 1
    updated_track = tracks[0]
    assert updated_track.track_id == initial_track.track_id
    assert updated_track.ts_event == later.timestamp
    assert updated_track.ts_ingest is not None
    assert updated_track.status in {
        RadarTrackStatusEnum.NEW,
        RadarTrackStatusEnum.TRACKED,
    }
    assert updated_track.quality >= initial_track.quality
    assert updated_track.transponder_mode == TransponderModeEnum.OFF


def test_track_store_drops_missed_tracks():
    store = RadarTrackStore(max_misses=1)
    start = datetime.now(UTC)
    first = _frame_with_detection(
        range_m=30.0,
        bearing_deg=0.0,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=10.0,
        timestamp=start,
    )
    store.process_frame(first)

    empty_frame = RadarFrameModel(
        sensor_id=first.sensor_id,
        timestamp=start + timedelta(milliseconds=200),
        detections=[],
    )
    tracks = store.process_frame(empty_frame)
    assert tracks[0].status == RadarTrackStatusEnum.LOST

    empty_frame_2 = RadarFrameModel(
        sensor_id=first.sensor_id,
        timestamp=start + timedelta(milliseconds=400),
        detections=[],
    )
    tracks = store.process_frame(empty_frame_2)
    assert len(tracks) == 0


def test_track_store_coasts_confirmed_tracks():
    store = RadarTrackStore(max_misses=2, min_hits_to_confirm=2)
    start = datetime.now(UTC)
    first = _frame_with_detection(
        range_m=30.0,
        bearing_deg=0.0,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=15.0,
        timestamp=start,
    )
    second = _frame_with_detection(
        range_m=30.5,
        bearing_deg=0.1,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=15.0,
        timestamp=start + timedelta(milliseconds=200),
    )
    track_1 = store.process_frame(first)[0]
    track_2 = store.process_frame(second)[0]
    assert track_2.track_id == track_1.track_id
    assert track_2.status == RadarTrackStatusEnum.TRACKED

    miss_1 = RadarFrameModel(
        sensor_id=first.sensor_id,
        timestamp=start + timedelta(milliseconds=400),
        detections=[],
    )
    tracks = store.process_frame(miss_1)
    assert len(tracks) == 1
    assert tracks[0].status == RadarTrackStatusEnum.COASTING
    assert tracks[0].miss_count == 1
    coast_quality_1 = tracks[0].quality

    miss_2 = RadarFrameModel(
        sensor_id=first.sensor_id,
        timestamp=start + timedelta(milliseconds=600),
        detections=[],
    )
    tracks = store.process_frame(miss_2)
    assert len(tracks) == 1
    assert tracks[0].status == RadarTrackStatusEnum.COASTING
    assert tracks[0].miss_count == 2
    assert tracks[0].quality <= coast_quality_1

    miss_3 = RadarFrameModel(
        sensor_id=first.sensor_id,
        timestamp=start + timedelta(milliseconds=800),
        detections=[],
    )
    tracks = store.process_frame(miss_3)
    assert len(tracks) == 0
