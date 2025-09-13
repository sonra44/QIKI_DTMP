from datetime import datetime, timedelta, timezone
from uuid import UUID as PyUUID, uuid4

from google.protobuf.timestamp_pb2 import Timestamp as ProtoTimestamp
from google.protobuf.duration_pb2 import Duration as ProtoDuration

from shared.models.core import (
    BiosStatus,
    DeviceStatus,
    DeviceStatusEnum,
    SensorData,
    SensorTypeEnum,
    Vector3,
    UnitEnum,
    ActuatorCommand,
    CommandTypeEnum,
    Proposal,
    ProposalTypeEnum,
    ProposalStatusEnum,
)

# Import Protobuf generated classes
from generated.bios_status_pb2 import BiosStatusReport as ProtoBiosStatusReport, DeviceStatus as ProtoDeviceStatus
from generated.common_types_pb2 import UUID as ProtoUUID, Vector3 as ProtoVector3, Unit as ProtoUnit, SensorType as ProtoSensorType
from generated.proposal_pb2 import Proposal as ProtoProposal
from generated.actuator_raw_out_pb2 import ActuatorCommand as ProtoActuatorCommand
from generated.sensor_raw_in_pb2 import SensorReading as ProtoSensorReading
from generated.fsm_state_pb2 import FsmStateSnapshot as ProtoFsmStateSnapshot
from services.q_core_agent.state.types import FsmSnapshotDTO, FsmState, TransitionStatus, TransitionDTO


# =============================================================================
#  Basic Type Converters
# =============================================================================
def proto_uuid_to_pydantic_uuid(proto_uuid: ProtoUUID) -> PyUUID:
    return PyUUID(proto_uuid.value) if proto_uuid.value else uuid4()

def pydantic_uuid_to_proto_uuid(pydantic_uuid: PyUUID) -> ProtoUUID:
    return ProtoUUID(value=str(pydantic_uuid))


def proto_timestamp_to_datetime(proto_ts: ProtoTimestamp) -> datetime:
    return proto_ts.ToDatetime(tzinfo=timezone.utc) if proto_ts.seconds or proto_ts.nanos else datetime.now(timezone.utc)

def datetime_to_proto_timestamp(dt: datetime) -> ProtoTimestamp:
    proto_ts = ProtoTimestamp()
    proto_ts.FromDatetime(dt.astimezone(timezone.utc))
    return proto_ts


def proto_duration_to_timedelta(proto_dur: ProtoDuration) -> timedelta:
    return proto_dur.ToTimedelta() if proto_dur.seconds or proto_dur.nanos else timedelta(0)

def timedelta_to_proto_duration(td: timedelta) -> ProtoDuration:
    proto_dur = ProtoDuration()
    proto_dur.FromTimedelta(td)
    return proto_dur


# =============================================================================
#  Enum Converters
# =============================================================================
def proto_device_status_to_pydantic_enum(proto_enum: ProtoDeviceStatus) -> DeviceStatusEnum:
    return DeviceStatusEnum(proto_enum)

def pydantic_device_status_to_proto_enum(pydantic_enum: DeviceStatusEnum) -> ProtoDeviceStatus:
    return ProtoDeviceStatus(pydantic_enum.value)

def proto_sensor_type_to_pydantic_enum(proto_enum: ProtoSensorType) -> SensorTypeEnum:
    return SensorTypeEnum(proto_enum)

def pydantic_sensor_type_to_proto_enum(pydantic_enum: SensorTypeEnum) -> ProtoSensorType:
    return ProtoSensorType(pydantic_enum.value)

def proto_unit_to_pydantic_enum(proto_enum: ProtoUnit) -> UnitEnum:
    return UnitEnum(proto_enum)

def pydantic_unit_to_proto_enum(pydantic_enum: UnitEnum) -> ProtoUnit:
    return ProtoUnit(pydantic_enum.value)

def proto_proposal_type_to_pydantic_enum(proto_enum: ProtoProposal.ProposalType) -> ProposalTypeEnum:
    return ProposalTypeEnum(proto_enum)

def pydantic_proposal_type_to_proto_enum(pydantic_enum: ProposalTypeEnum) -> ProtoProposal.ProposalType:
    return ProtoProposal.ProposalType(pydantic_enum.value)

def proto_proposal_status_to_pydantic_enum(proto_enum: ProtoProposal.ProposalStatus) -> ProposalStatusEnum:
    return ProposalStatusEnum(proto_enum)

def pydantic_proposal_status_to_proto_enum(pydantic_enum: ProposalStatusEnum) -> ProtoProposal.ProposalStatus:
    return ProtoProposal.ProposalStatus(pydantic_enum.value)

def proto_command_type_to_pydantic_enum(proto_enum: ProtoActuatorCommand.CommandType) -> CommandTypeEnum:
    return CommandTypeEnum(proto_enum)

def pydantic_command_type_to_proto_enum(pydantic_enum: CommandTypeEnum) -> ProtoActuatorCommand.CommandType:
    return ProtoActuatorCommand.CommandType(pydantic_enum.value)


# =============================================================================
#  Complex Model Converters
# =============================================================================
def proto_vector3_to_pydantic_vector3(proto_vec: ProtoVector3) -> Vector3:
    return Vector3(x=proto_vec.x, y=proto_vec.y, z=proto_vec.z)

def pydantic_vector3_to_proto_vector3(pydantic_vec: Vector3) -> ProtoVector3:
    return ProtoVector3(x=pydantic_vec.x, y=pydantic_vec.y, z=pydantic_vec.z)


def proto_device_status_to_pydantic_device_status(proto_ds: ProtoDeviceStatus) -> DeviceStatus:
    return DeviceStatus(
        device_id=proto_ds.device_id,
        device_name=proto_ds.device_name,
        status=proto_device_status_to_pydantic_enum(proto_ds.status),
        status_message=proto_ds.status_message if proto_ds.status_message else None,
    )

def pydantic_device_status_to_proto_device_status(pydantic_ds: DeviceStatus) -> ProtoDeviceStatus:
    return ProtoDeviceStatus(
        device_id=pydantic_ds.device_id,
        device_name=pydantic_ds.device_name,
        status=pydantic_device_status_to_proto_enum(pydantic_ds.status),
        status_message=pydantic_ds.status_message if pydantic_ds.status_message else "",
    )


def proto_bios_status_report_to_pydantic_bios_status(proto_bsr: ProtoBiosStatusReport) -> BiosStatus:
    return BiosStatus(
        bios_version=proto_bsr.bios_version,
        firmware_version=proto_bsr.firmware_version,
        post_results=[
            proto_device_status_to_pydantic_device_status(pr)
            for pr in proto_bsr.post_results
        ],
        timestamp=proto_timestamp_to_datetime(proto_bsr.timestamp),
    )

def pydantic_bios_status_to_proto_bios_status_report(pydantic_bs: BiosStatus) -> ProtoBiosStatusReport:
    return ProtoBiosStatusReport(
        bios_version=pydantic_bs.bios_version,
        firmware_version=pydantic_bs.firmware_version,
        post_results=[
            pydantic_device_status_to_proto_device_status(pr)
            for pr in pydantic_bs.post_results
        ],
        timestamp=datetime_to_proto_timestamp(pydantic_bs.timestamp),
    )


def proto_actuator_command_to_pydantic_actuator_command(proto_ac: ProtoActuatorCommand) -> ActuatorCommand:
    pydantic_ac = ActuatorCommand(
        command_id=proto_uuid_to_pydantic_uuid(proto_ac.command_id),
        actuator_id=proto_uuid_to_pydantic_uuid(proto_ac.actuator_id),
        timestamp=proto_timestamp_to_datetime(proto_ac.timestamp),
        unit=proto_unit_to_pydantic_enum(proto_ac.unit),
        command_type=proto_command_type_to_pydantic_enum(proto_ac.command_type),
        confidence=proto_ac.confidence,
        timeout_ms=proto_ac.timeout_ms if proto_ac.HasField('timeout_ms') else None,
        ack_required=proto_ac.ack_required,
        retry_count=proto_ac.retry_count,
    )
    # Handle oneof command_value
    if proto_ac.HasField('float_value'):
        pydantic_ac.float_value = proto_ac.float_value
    elif proto_ac.HasField('int_value'):
        pydantic_ac.int_value = proto_ac.int_value
    elif proto_ac.HasField('bool_value'):
        pydantic_ac.bool_value = proto_ac.bool_value
    elif proto_ac.HasField('vector_value'):
        pydantic_ac.vector_value = proto_vector3_to_pydantic_vector3(proto_ac.vector_value)
    return pydantic_ac

def pydantic_actuator_command_to_proto_actuator_command(pydantic_ac: ActuatorCommand) -> ProtoActuatorCommand:
    proto_ac = ProtoActuatorCommand(
        command_id=pydantic_uuid_to_proto_uuid(pydantic_ac.command_id),
        actuator_id=pydantic_uuid_to_proto_uuid(pydantic_ac.actuator_id),
        timestamp=datetime_to_proto_timestamp(pydantic_ac.timestamp),
        unit=pydantic_unit_to_proto_enum(pydantic_ac.unit),
        command_type=pydantic_command_type_to_proto_enum(pydantic_ac.command_type),
        confidence=pydantic_ac.confidence,
        ack_required=pydantic_ac.ack_required,
        retry_count=pydantic_ac.retry_count,
    )
    if pydantic_ac.timeout_ms is not None:
        proto_ac.timeout_ms = pydantic_ac.timeout_ms

    # Handle oneof command_value
    if pydantic_ac.float_value is not None:
        proto_ac.float_value = pydantic_ac.float_value
    elif pydantic_ac.int_value is not None:
        proto_ac.int_value = pydantic_ac.int_value
    elif pydantic_ac.bool_value is not None:
        proto_ac.bool_value = pydantic_ac.bool_value
    elif pydantic_ac.vector_value is not None:
        proto_ac.vector_value.CopyFrom(pydantic_vector3_to_proto_vector3(pydantic_ac.vector_value))
    return proto_ac


def proto_proposal_to_pydantic_proposal(proto_p: ProtoProposal) -> Proposal:
    return Proposal(
        proposal_id=proto_uuid_to_pydantic_uuid(proto_p.proposal_id),
        source_module_id=proto_p.source_module_id,
        timestamp=proto_timestamp_to_datetime(proto_p.timestamp),
        proposed_actions=[
            proto_actuator_command_to_pydantic_actuator_command(pa)
            for pa in proto_p.proposed_actions
        ],
        justification=proto_p.justification,
        priority=proto_p.priority,
        expected_duration=proto_duration_to_timedelta(proto_p.expected_duration) if proto_p.HasField('expected_duration') else None,
        type=proto_proposal_type_to_pydantic_enum(proto_p.type),
        metadata=dict(proto_p.metadata),
        confidence=proto_p.confidence,
        status=proto_proposal_status_to_pydantic_enum(proto_p.status),
        depends_on=[proto_uuid_to_pydantic_uuid(u) for u in proto_p.depends_on],
        conflicts_with=[proto_uuid_to_pydantic_uuid(u) for u in proto_p.conflicts_with],
        proposal_signature=proto_p.proposal_signature if proto_p.proposal_signature else None,
    )

def pydantic_proposal_to_proto_proposal(pydantic_p: Proposal) -> ProtoProposal:
    proto_p = ProtoProposal(
        proposal_id=pydantic_uuid_to_proto_uuid(pydantic_p.proposal_id),
        source_module_id=pydantic_p.source_module_id,
        timestamp=datetime_to_proto_timestamp(pydantic_p.timestamp),
        proposed_actions=[
            pydantic_actuator_command_to_proto_actuator_command(pa)
            for pa in pydantic_p.proposed_actions
        ],
        justification=pydantic_p.justification,
        priority=pydantic_p.priority,
        type=pydantic_proposal_type_to_proto_enum(pydantic_p.type),
        metadata=pydantic_p.metadata,
        confidence=pydantic_p.confidence,
        status=pydantic_proposal_status_to_proto_enum(pydantic_p.status),
        depends_on=[pydantic_uuid_to_proto_uuid(u) for u in pydantic_p.depends_on],
        conflicts_with=[pydantic_uuid_to_proto_uuid(u) for u in pydantic_p.conflicts_with],
    )
    if pydantic_p.expected_duration is not None:
        proto_p.expected_duration.CopyFrom(timedelta_to_proto_duration(pydantic_p.expected_duration))
    if pydantic_p.proposal_signature is not None:
        proto_p.proposal_signature = pydantic_p.proposal_signature
    return proto_p


def proto_sensor_reading_to_pydantic_sensor_data(proto_sr: ProtoSensorReading) -> SensorData:
    """Convert Proto SensorReading to Pydantic SensorData.

    Протокол SensorReading использует oneof `sensor_data` с полями:
    - vector_data (Vector3)
    - scalar_data (float)
    - binary_data (bytes)

    В текущем MVP отсутствуют поля `matrix_data`, `string_data`, `metadata`, `quality_score`.
    Поэтому безопасно маппим только доступные поля и ставим дефолты.
    """
    data_kind = proto_sr.WhichOneof('sensor_data')
    scalar = None
    vector = None

    if data_kind == 'scalar_data':
        scalar = proto_sr.scalar_data
    elif data_kind == 'vector_data':
        vec = proto_sr.vector_data
        # vec — это message Vector3, соберём список [x, y, z]
        vector = [vec.x, vec.y, vec.z]
    # binary_data игнорируем для текущего слоя абстракции

    return SensorData(
        sensor_id=str(proto_uuid_to_pydantic_uuid(proto_sr.sensor_id)),
        sensor_type=proto_sensor_type_to_pydantic_enum(proto_sr.sensor_type),
        scalar_data=scalar,
        vector_data=vector,
        metadata={},
        quality_score=1.0,
    )

def pydantic_sensor_data_to_proto_sensor_reading(pydantic_sd: SensorData) -> ProtoSensorReading:
    proto_sr = ProtoSensorReading(
        sensor_id=pydantic_uuid_to_proto_uuid(pydantic_sd.sensor_id),
        sensor_type=pydantic_sensor_type_to_proto_enum(pydantic_sd.sensor_type),
        metadata=pydantic_sd.metadata,
        quality_score=pydantic_sd.quality_score,
    )
    if pydantic_sd.scalar_data is not None:
        proto_sr.scalar_data = pydantic_sd.scalar_data
    if pydantic_sd.vector_data is not None:
        proto_sr.vector_data.extend(pydantic_sd.vector_data)
    if pydantic_sd.matrix_data is not None:
        # Matrix data in protobuf is repeated message, so we need to iterate and add rows
        for row in pydantic_sd.matrix_data:
            proto_sr.matrix_data.add().values.extend(row)
    if pydantic_sd.string_data is not None:
        proto_sr.string_data = pydantic_sd.string_data
    return proto_sr


def proto_fsm_state_snapshot_to_pydantic_fsm_snapshot_dto(proto_snapshot: ProtoFsmStateSnapshot) -> FsmSnapshotDTO:
    history = []
    for transition in proto_snapshot.history:
        history.append(TransitionDTO(
            from_state=FsmState(transition.from_state),
            to_state=FsmState(transition.to_state),
            trigger_event=transition.trigger_event,
            status=TransitionStatus(transition.status),
            error_message=transition.error_message,
            ts_mono=transition.timestamp.ToDatetime().timestamp(), # Using timestamp for both for now
            ts_wall=transition.timestamp.ToDatetime().timestamp() # Using timestamp for both for now
        ))

    # Extract version from state_metadata, default to 0 if not found or invalid
    version = int(proto_snapshot.state_metadata.get("dto_version", 0))

    return FsmSnapshotDTO(
        version=version, # Added version
        state=FsmState(proto_snapshot.current_state),
        ts_mono=proto_snapshot.timestamp.ToDatetime().timestamp(), # Changed
        ts_wall=proto_snapshot.timestamp.ToDatetime().timestamp(),
        snapshot_id=proto_snapshot.snapshot_id.value,
        fsm_instance_id=proto_snapshot.fsm_instance_id.value,
        source_module=proto_snapshot.source_module,
        attempt_count=proto_snapshot.attempt_count,
        history=tuple(history),
        context_data=dict(proto_snapshot.context_data),
        state_metadata=dict(proto_snapshot.state_metadata)
    )

def pydantic_fsm_snapshot_dto_to_proto_fsm_state_snapshot(pydantic_dto: FsmSnapshotDTO) -> ProtoFsmStateSnapshot:
    proto_snapshot = ProtoFsmStateSnapshot(
        current_state=pydantic_dto.state.value, # Convert enum to its integer value
        snapshot_id=ProtoUUID(value=str(pydantic_dto.snapshot_id)),
        fsm_instance_id=ProtoUUID(value=str(pydantic_dto.fsm_instance_id)),
        source_module=pydantic_dto.source_module,
        attempt_count=pydantic_dto.attempt_count,
        context_data=pydantic_dto.context_data,
        state_metadata=pydantic_dto.state_metadata
    )

    # Handle optional fields
    # if pydantic_dto.prev_state is not None:
    #     proto_snapshot.prev_state = pydantic_dto.prev_state.value

    # Handle history
    for transition in pydantic_dto.history:
        proto_transition = proto_snapshot.history.add()
        proto_transition.from_state = transition.from_state.value
        proto_transition.to_state = transition.to_state.value
        proto_transition.trigger_event = transition.trigger_event
        proto_transition.status = transition.status.value
        proto_transition.error_message = transition.error_message
        # Convert timestamps back to Protobuf Timestamp
        # Convert timestamps back to Protobuf Timestamp
        # FromSeconds expects an integer, so split float into seconds and nanos
        seconds = int(transition.ts_wall)
        nanos = int((transition.ts_wall - seconds) * 1_000_000_000)
        proto_transition.timestamp.FromSeconds(seconds)
        proto_transition.timestamp.nanos = nanos

    # Convert timestamps for the snapshot itself
    seconds = int(pydantic_dto.ts_wall)
    nanos = int((pydantic_dto.ts_wall - seconds) * 1_000_000_000)
    proto_snapshot.timestamp.FromSeconds(seconds)
    proto_snapshot.timestamp.nanos = nanos

    return proto_snapshot

    return proto_snapshot
