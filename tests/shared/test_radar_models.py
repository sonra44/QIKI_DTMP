import pytest
from uuid import uuid4

from qiki.shared.models.radar import (
    RadarDetectionModel,
    RadarFrameModel,
    RadarTrackModel,
    ObjectTypeEnum,
    FriendFoeEnum,
    TransponderModeEnum,
    RadarTrackStatusEnum,
    Vector3Model,
)
from qiki.shared.converters.radar_proto_pydantic import (
    model_frame_to_proto,
    proto_frame_to_model,
    model_track_to_proto,
    proto_track_to_model,
)


def test_detection_validators():
    # bearing out of range
    with pytest.raises(ValueError):
        RadarDetectionModel(
            range_m=100,
            bearing_deg=360.0,
            elev_deg=0.0,
            vr_mps=0.0,
            snr_db=10.0,
            rcs_dbsm=0.0,
        )
    # elevation out of range
    with pytest.raises(ValueError):
        RadarDetectionModel(
            range_m=100,
            bearing_deg=10.0,
            elev_deg=100.0,
            vr_mps=0.0,
            snr_db=10.0,
            rcs_dbsm=0.0,
        )
    # snr negative
    with pytest.raises(ValueError):
        RadarDetectionModel(
            range_m=100,
            bearing_deg=10.0,
            elev_deg=0.0,
            vr_mps=0.0,
            snr_db=-1.0,
            rcs_dbsm=0.0,
        )


def test_frame_conversion_roundtrip():
    det = RadarDetectionModel(
        range_m=100,
        bearing_deg=10.0,
        elev_deg=-5.0,
        vr_mps=-12.3,
        snr_db=15.0,
        rcs_dbsm=1.2,
        transponder_on=True,
        transponder_mode=TransponderModeEnum.ON,
        transponder_id="ALLY-001",
    )
    frame = RadarFrameModel(sensor_id=uuid4(), detections=[det])
    proto = model_frame_to_proto(frame)
    back = proto_frame_to_model(proto)
    assert back.schema_version == frame.schema_version
    assert back.sensor_id == frame.sensor_id
    assert len(back.detections) == 1
    back_det = back.detections[0]
    assert back_det.bearing_deg == det.bearing_deg
    assert back_det.transponder_on is True
    assert back_det.transponder_mode == det.transponder_mode
    assert back_det.transponder_id == det.transponder_id


def test_track_conversion_roundtrip():
    track = RadarTrackModel(
        object_type=ObjectTypeEnum.DRONE,
        iff=FriendFoeEnum.UNKNOWN,
        transponder_on=True,
        transponder_mode=TransponderModeEnum.SPOOF,
        transponder_id="SPOOF-42",
        status=RadarTrackStatusEnum.TRACKED,
        quality=0.8,
        range_m=500.0,
        bearing_deg=123.0,
        elev_deg=5.0,
        vr_mps=-25.0,
        snr_db=20.0,
        rcs_dbsm=2.5,
        position=Vector3Model(x=100.0, y=50.0, z=10.0),
        velocity=Vector3Model(x=-1.0, y=0.5, z=0.0),
        position_covariance=[1.0, 0.0, 0.0, 1.5, 0.0, 2.0],
        velocity_covariance=[0.3, 0.0, 0.0, 0.4, 0.0, 0.5],
        age_s=4.2,
        miss_count=1,
    )
    proto = model_track_to_proto(track)
    back = proto_track_to_model(proto)
    assert back.object_type == track.object_type
    assert back.iff == track.iff
    assert back.range_m == track.range_m
    assert back.bearing_deg == track.bearing_deg
    assert back.elev_deg == track.elev_deg
    assert back.snr_db == track.snr_db
    assert back.transponder_mode == track.transponder_mode
    assert back.transponder_id == track.transponder_id
    assert back.status == track.status
    assert back.position == track.position
    assert back.velocity == track.velocity
    assert back.position_covariance == track.position_covariance
    assert back.velocity_covariance == track.velocity_covariance
    assert back.age_s == track.age_s
    assert back.miss_count == track.miss_count
