from __future__ import annotations

from generated.radar.v1.radar_pb2 import (
    RadarDetection as ProtoRadarDetection,
    RadarFrame as ProtoRadarFrame,
    RadarTrack as ProtoRadarTrack,
)

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
from qiki.shared.converters.protobuf_pydantic import (
    proto_uuid_to_pydantic_uuid,
    pydantic_uuid_to_proto_uuid,
    proto_timestamp_to_datetime,
    datetime_to_proto_timestamp,
)


def proto_detection_to_model(p: ProtoRadarDetection) -> RadarDetectionModel:
    return RadarDetectionModel(
        range_m=p.range_m,
        bearing_deg=p.bearing_deg,
        elev_deg=p.elev_deg,
        vr_mps=p.vr_mps,
        snr_db=p.snr_db,
        rcs_dbsm=p.rcs_dbsm,
        transponder_on=p.transponder_on,
        transponder_mode=TransponderModeEnum(p.transponder_mode),
        transponder_id=p.transponder_id or None,
    )


def model_detection_to_proto(m: RadarDetectionModel) -> ProtoRadarDetection:
    return ProtoRadarDetection(
        range_m=float(m.range_m),
        bearing_deg=float(m.bearing_deg),
        elev_deg=float(m.elev_deg),
        vr_mps=float(m.vr_mps),
        snr_db=float(m.snr_db),
        rcs_dbsm=float(m.rcs_dbsm),
        transponder_on=bool(m.transponder_on),
        transponder_mode=m.transponder_mode.value,
        transponder_id=m.transponder_id or "",
    )


def proto_frame_to_model(p: ProtoRadarFrame) -> RadarFrameModel:
    return RadarFrameModel(
        schema_version=p.schema_version,
        frame_id=proto_uuid_to_pydantic_uuid(p.frame_id),
        sensor_id=proto_uuid_to_pydantic_uuid(p.sensor_id),
        timestamp=proto_timestamp_to_datetime(p.timestamp),
        detections=[proto_detection_to_model(d) for d in p.detections],
    )


def model_frame_to_proto(m: RadarFrameModel) -> ProtoRadarFrame:
    p = ProtoRadarFrame(
        schema_version=int(m.schema_version),
        frame_id=pydantic_uuid_to_proto_uuid(m.frame_id),
        sensor_id=pydantic_uuid_to_proto_uuid(m.sensor_id),
    )
    p.timestamp.CopyFrom(datetime_to_proto_timestamp(m.timestamp))
    p.detections.extend([model_detection_to_proto(d) for d in m.detections])
    return p


def proto_track_to_model(p: ProtoRadarTrack) -> RadarTrackModel:
    position = None
    if p.HasField("position"):
        position = Vector3Model(x=p.position.x, y=p.position.y, z=p.position.z)

    velocity = None
    if p.HasField("velocity"):
        velocity = Vector3Model(x=p.velocity.x, y=p.velocity.y, z=p.velocity.z)

    return RadarTrackModel(
        schema_version=p.schema_version,
        track_id=proto_uuid_to_pydantic_uuid(p.track_id),
        object_type=ObjectTypeEnum(p.object_type),
        iff=FriendFoeEnum(p.iff),
        transponder_on=p.transponder_on,
        quality=p.quality,
        range_m=p.range_m,
        bearing_deg=p.bearing_deg,
        elev_deg=p.elev_deg,
        vr_mps=p.vr_mps,
        snr_db=p.snr_db,
        rcs_dbsm=p.rcs_dbsm,
        timestamp=proto_timestamp_to_datetime(p.timestamp),
        transponder_mode=TransponderModeEnum(p.transponder_mode),
        transponder_id=p.transponder_id or None,
        status=RadarTrackStatusEnum(p.status),
        position=position,
        velocity=velocity,
        position_covariance=list(p.position_covariance) or None,
        velocity_covariance=list(p.velocity_covariance) or None,
        age_s=p.age_s,
        miss_count=p.miss_count,
    )


def model_track_to_proto(m: RadarTrackModel) -> ProtoRadarTrack:
    p = ProtoRadarTrack(
        schema_version=int(m.schema_version),
        track_id=pydantic_uuid_to_proto_uuid(m.track_id),
        object_type=m.object_type.value,
        iff=m.iff.value,
        transponder_on=bool(m.transponder_on),
        quality=float(m.quality),
        range_m=float(m.range_m),
        bearing_deg=float(m.bearing_deg),
        elev_deg=float(m.elev_deg),
        vr_mps=float(m.vr_mps),
        snr_db=float(m.snr_db),
        rcs_dbsm=float(m.rcs_dbsm),
    )
    p.timestamp.CopyFrom(datetime_to_proto_timestamp(m.timestamp))
    p.transponder_mode = m.transponder_mode.value
    p.transponder_id = m.transponder_id or ""
    p.status = m.status.value
    if m.position is not None:
        p.position.x = float(m.position.x)
        p.position.y = float(m.position.y)
        p.position.z = float(m.position.z)
    if m.velocity is not None:
        p.velocity.x = float(m.velocity.x)
        p.velocity.y = float(m.velocity.y)
        p.velocity.z = float(m.velocity.z)
    if m.position_covariance:
        p.position_covariance.extend(float(v) for v in m.position_covariance)
    if m.velocity_covariance:
        p.velocity_covariance.extend(float(v) for v in m.velocity_covariance)
    p.age_s = float(m.age_s)
    p.miss_count = int(m.miss_count)
    return p
