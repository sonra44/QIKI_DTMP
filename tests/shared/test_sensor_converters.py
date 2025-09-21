from uuid import uuid4

from pytest import approx, raises
from pydantic import ValidationError

from qiki.shared.models.core import SensorData, SensorTypeEnum
from qiki.shared.models.radar import (
    RadarFrameModel,
    RadarDetectionModel,
    RadarTrackModel,
    ObjectTypeEnum,
    FriendFoeEnum,
    TransponderModeEnum,
    RadarTrackStatusEnum,
    Vector3Model,
)
from qiki.shared.converters.protobuf_pydantic import (
    pydantic_sensor_data_to_proto_sensor_reading,
    proto_sensor_reading_to_pydantic_sensor_data,
)
from generated.sensor_raw_in_pb2 import SensorReading


def test_pydantic_sensor_to_proto_scalar_only():
    sd = SensorData(
        sensor_id="123e4567-e89b-12d3-a456-426614174000",
        sensor_type=SensorTypeEnum.LIDAR,
        scalar_data=12.34,
    )
    proto = pydantic_sensor_data_to_proto_sensor_reading(sd)
    assert proto.sensor_id.value == "123e4567-e89b-12d3-a456-426614174000"
    assert proto.sensor_type == sd.sensor_type.value
    assert proto.scalar_data == approx(12.34, rel=1e-6, abs=1e-6)
    # vector should be unset in oneof
    assert proto.WhichOneof("sensor_data") == "scalar_data"


def test_pydantic_sensor_to_proto_vector3():
    sd = SensorData(
        sensor_id="00000000-0000-0000-0000-000000000001",
        sensor_type=SensorTypeEnum.IMU,
        vector_data=[1.0, 2.0, 3.0],
    )
    proto = pydantic_sensor_data_to_proto_sensor_reading(sd)
    assert proto.sensor_id.value == "00000000-0000-0000-0000-000000000001"
    assert proto.sensor_type == sd.sensor_type.value
    assert proto.vector_data.x == 1.0
    assert proto.vector_data.y == 2.0
    assert proto.vector_data.z == 3.0
    assert proto.WhichOneof("sensor_data") == "vector_data"


def test_pydantic_sensor_to_proto_radar_frame():
    det = RadarDetectionModel(
        range_m=50.0,
        bearing_deg=45.0,
        elev_deg=2.0,
        vr_mps=-5.0,
        snr_db=12.0,
        rcs_dbsm=0.5,
        transponder_on=True,
        transponder_mode=TransponderModeEnum.ON,
        transponder_id="ALLY-123",
    )
    frame = RadarFrameModel(sensor_id=uuid4(), detections=[det])
    sd = SensorData(
        sensor_id=str(frame.sensor_id),
        sensor_type=SensorTypeEnum.RADAR,
        radar_frame=frame,
    )

    proto = pydantic_sensor_data_to_proto_sensor_reading(sd)
    assert proto.sensor_type == SensorTypeEnum.RADAR.value
    assert proto.WhichOneof("sensor_data") == "radar_data"
    proto_det = proto.radar_data.detections[0]
    assert proto_det.bearing_deg == approx(45.0)
    assert proto_det.transponder_mode == TransponderModeEnum.ON.value
    assert proto_det.transponder_id == "ALLY-123"


def test_proto_to_pydantic_includes_radar_frame():
    det = RadarDetectionModel(
        range_m=75.0,
        bearing_deg=15.0,
        elev_deg=1.0,
        vr_mps=3.0,
        snr_db=9.0,
        rcs_dbsm=0.8,
        transponder_mode=TransponderModeEnum.SILENT,
        transponder_id="ALLY-777",
    )
    frame = RadarFrameModel(sensor_id=uuid4(), detections=[det])
    proto_frame = pydantic_sensor_data_to_proto_sensor_reading(
        SensorData(
            sensor_id=str(frame.sensor_id),
            sensor_type=SensorTypeEnum.RADAR,
            radar_frame=frame,
        )
    ).radar_data
    proto = SensorReading(
        sensor_type=SensorTypeEnum.RADAR.value,
        radar_data=proto_frame,
    )
    proto.sensor_id.value = str(frame.sensor_id)

    converted = proto_sensor_reading_to_pydantic_sensor_data(proto)
    assert converted.sensor_type is SensorTypeEnum.RADAR
    assert converted.radar_frame is not None
    assert converted.radar_frame.detections[0].range_m == approx(75.0)


def test_pydantic_sensor_to_proto_radar_track():
    track = RadarTrackModel(
        object_type=ObjectTypeEnum.DRONE,
        iff=FriendFoeEnum.UNKNOWN,
        transponder_on=True,
        transponder_mode=TransponderModeEnum.SPOOF,
        transponder_id="SPOOF-10",
        status=RadarTrackStatusEnum.TRACKED,
        quality=0.9,
        range_m=120.0,
        bearing_deg=33.0,
        elev_deg=5.0,
        vr_mps=-12.0,
        snr_db=14.0,
        rcs_dbsm=0.7,
        position=Vector3Model(x=1.0, y=2.0, z=3.0),
        velocity=Vector3Model(x=0.1, y=0.2, z=0.3),
        position_covariance=[0.1, 0.0, 0.0, 0.2, 0.0, 0.3],
        velocity_covariance=[0.4, 0.0, 0.0, 0.5, 0.0, 0.6],
        age_s=3.4,
        miss_count=2,
    )
    sd = SensorData(
        sensor_id=str(track.track_id),
        sensor_type=SensorTypeEnum.RADAR,
        radar_track=track,
    )

    proto = pydantic_sensor_data_to_proto_sensor_reading(sd)
    assert proto.sensor_type == SensorTypeEnum.RADAR.value
    assert proto.WhichOneof("sensor_data") == "radar_track"
    assert proto.radar_track.range_m == approx(120.0)
    assert proto.radar_track.transponder_mode == TransponderModeEnum.SPOOF.value
    assert proto.radar_track.status == RadarTrackStatusEnum.TRACKED.value
    assert list(proto.radar_track.position_covariance) == [0.1, 0.0, 0.0, 0.2, 0.0, 0.3]
    assert proto.radar_track.age_s == approx(3.4)
    assert proto.radar_track.miss_count == 2


def test_proto_to_pydantic_includes_radar_track():
    track = RadarTrackModel(
        object_type=ObjectTypeEnum.SHIP,
        iff=FriendFoeEnum.FRIEND,
        transponder_on=False,
        transponder_mode=TransponderModeEnum.OFF,
        status=RadarTrackStatusEnum.NEW,
        quality=0.6,
        range_m=80.0,
        bearing_deg=180.0,
        elev_deg=0.0,
        vr_mps=5.0,
        snr_db=18.0,
        rcs_dbsm=1.1,
        position=Vector3Model(x=4.0, y=-1.0, z=0.0),
        velocity=Vector3Model(x=0.0, y=0.0, z=0.0),
    )
    proto_track = pydantic_sensor_data_to_proto_sensor_reading(
        SensorData(
            sensor_id=str(track.track_id),
            sensor_type=SensorTypeEnum.RADAR,
            radar_track=track,
        )
    ).radar_track
    proto = SensorReading(
        sensor_type=SensorTypeEnum.RADAR.value,
        radar_track=proto_track,
    )
    proto.sensor_id.value = str(track.track_id)

    converted = proto_sensor_reading_to_pydantic_sensor_data(proto)
    assert converted.sensor_type is SensorTypeEnum.RADAR
    assert converted.radar_track is not None
    assert converted.radar_track.range_m == approx(80.0)
    assert converted.radar_track.status == RadarTrackStatusEnum.NEW


def test_sensor_data_rejects_frame_and_track_together():
    det = RadarDetectionModel(
        range_m=10.0,
        bearing_deg=10.0,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=5.0,
        rcs_dbsm=0.1,
    )
    frame = RadarFrameModel(sensor_id=uuid4(), detections=[det])
    track = RadarTrackModel(
        object_type=ObjectTypeEnum.DRONE,
        iff=FriendFoeEnum.UNKNOWN,
        transponder_on=False,
        quality=0.5,
        range_m=10.0,
        bearing_deg=10.0,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=5.0,
        rcs_dbsm=0.1,
    )
    with raises(ValidationError):
        SensorData(
            sensor_id=str(frame.sensor_id),
            sensor_type=SensorTypeEnum.RADAR,
            radar_frame=frame,
            radar_track=track,
        )
