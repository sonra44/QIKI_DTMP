"""
Pydantic модели для QIKI DTMP FastStream миграции.
Определяют основную структуру данных, заменяя Proto+DTO связку.
Версия: 1.0
Дата: 2025-08-19
"""

import time
from datetime import datetime, UTC, timedelta
from enum import IntEnum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field, model_validator, ConfigDict
from qiki.shared.models.radar import RadarFrameModel, RadarTrackModel
from pydantic.alias_generators import to_camel


# =============================================================================
#  Базовая конфигурация моделей
# =============================================================================
class ConfigModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        validate_assignment=True,
    )


# =============================================================================
#  Перечисления (Enums)
# =============================================================================
class FsmStateEnum(IntEnum):
    OFFLINE = 0
    BOOTING = 1
    IDLE = 2
    RUNNING = 3
    PAUSED = 4
    ERROR = 5
    TERMINATING = 6


class DeviceStatusEnum(IntEnum):
    UNKNOWN = 0
    OK = 1
    DEGRADED = 2
    ERROR = 3


class SensorTypeEnum(IntEnum):
    OTHER = 0
    LIDAR = 1
    IMU = 2
    CAMERA = 3
    GPS = 4
    THERMAL = 5
    RADAR = 6


class UnitEnum(IntEnum):
    UNIT_UNSPECIFIED = 0
    METERS = 1
    DEGREES = 2
    PERCENT = 3
    VOLTS = 4
    AMPS = 5
    WATTS = 6
    MILLISECONDS = 7
    KELVIN = 8
    BAR = 9


class ProposalTypeEnum(IntEnum):
    PROPOSAL_TYPE_UNSPECIFIED = 0
    SAFETY = 1
    PLANNING = 2
    DIAGNOSTICS = 3
    EXPLORATION = 4


class ProposalStatusEnum(IntEnum):
    PROPOSAL_STATUS_UNSPECIFIED = 0
    PENDING = 1
    ACCEPTED = 2
    REJECTED = 3
    EXECUTED = 4
    EXPIRED = 5


class CommandTypeEnum(IntEnum):
    COMMAND_TYPE_UNSPECIFIED = 0
    SET_VELOCITY = 1
    ROTATE = 2
    ENABLE = 3
    DISABLE = 4
    SET_MODE = 5


# =============================================================================
#  Вспомогательные и вложенные модели
# =============================================================================
class Vector3(ConfigModel):
    x: float
    y: float
    z: float


class MessageMetadata(ConfigModel):
    message_id: UUID = Field(default_factory=uuid4)
    correlation_id: Optional[UUID] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message_type: str = ""
    source: str = "unknown"
    destination: str = "unknown"


class FsmTransition(ConfigModel):
    event_name: str
    from_state: FsmStateEnum
    to_state: FsmStateEnum
    ts_mono: float = Field(default_factory=time.monotonic)
    ts_wall: float = Field(default_factory=time.time)


class DeviceStatus(ConfigModel):
    device_id: str
    device_name: str
    status: DeviceStatusEnum = DeviceStatusEnum.UNKNOWN
    status_message: Optional[str] = None


# =============================================================================
#  Основные модели данных (Snapshots)
# =============================================================================
class FsmStateSnapshot(ConfigModel):
    current_state: FsmStateEnum
    previous_state: FsmStateEnum
    last_transition: Optional[FsmTransition] = None
    history: List[FsmTransition] = Field(default_factory=list)
    context_data: Dict[str, str] = Field(default_factory=dict)
    state_metadata: Dict[str, str] = Field(default_factory=dict)
    ts_mono: float = Field(default_factory=time.monotonic)
    ts_wall: float = Field(default_factory=time.time)


class BiosStatus(ConfigModel):
    bios_version: str
    firmware_version: str
    post_results: List[DeviceStatus]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @computed_field
    def all_systems_go(self) -> bool:
        """Вычисляет общее состояние системы на основе статусов устройств."""
        if not self.post_results:
            return False
        return all(device.status == DeviceStatusEnum.OK for device in self.post_results)


class SensorData(ConfigModel):
    sensor_id: str
    sensor_type: SensorTypeEnum
    scalar_data: Optional[float] = None
    vector_data: Optional[List[float]] = None
    matrix_data: Optional[List[List[float]]] = None
    string_data: Optional[str] = None
    radar_frame: Optional[RadarFrameModel] = None
    radar_track: Optional[RadarTrackModel] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    quality_score: float = Field(ge=0.0, le=1.0, default=1.0)

    @model_validator(mode="after")
    def validate_data_presence(self):
        data_fields = [
            self.scalar_data,
            self.vector_data,
            self.matrix_data,
            self.string_data,
            self.radar_frame,
            self.radar_track,
        ]
        set_count = sum(field is not None for field in data_fields)
        if set_count == 0:
            raise ValueError("Sensor data must have at least one data field")
        if set_count > 1:
            raise ValueError(
                "Sensor data must provide exactly one payload representation"
            )
        return self




# =============================================================================
#  Модели для сообщений (запросы и ответы)
# =============================================================================
class CommandMessage(ConfigModel):
    command_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metadata: MessageMetadata


class ResponseMessage(ConfigModel):
    request_id: UUID
    metadata: MessageMetadata
    payload: Dict[str, Any]
    error: Optional[str] = None
    success: bool = True

    @model_validator(mode="after")
    def validate_response_consistency(self):
        if not self.success and not self.error:
            raise ValueError("Error message is required when success=False")
        if self.success and self.error:
            raise ValueError("Success response should not have error message")
        return self


class ActuatorCommand(ConfigModel):
    command_id: UUID = Field(default_factory=uuid4)
    actuator_id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # OneOf command_value
    float_value: Optional[float] = None
    int_value: Optional[int] = None
    bool_value: Optional[bool] = None
    vector_value: Optional[Vector3] = None

    unit: UnitEnum = UnitEnum.UNIT_UNSPECIFIED
    command_type: CommandTypeEnum
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    timeout_ms: Optional[int] = None
    ack_required: bool = False
    retry_count: int = 0

    @model_validator(mode="after")
    def validate_command_value(self):
        set_values = [
            self.float_value,
            self.int_value,
            self.bool_value,
            self.vector_value,
        ]
        if sum(1 for v in set_values if v is not None) != 1:
            raise ValueError(
                "Exactly one of float_value, int_value, bool_value, "
                "or vector_value must be set"
            )
        return self


class Proposal(ConfigModel):
    proposal_id: UUID = Field(default_factory=uuid4)
    source_module_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    proposed_actions: List[ActuatorCommand] = Field(default_factory=list)
    justification: str
    priority: float = Field(ge=0.0, le=1.0)
    expected_duration: Optional[timedelta] = None
    type: ProposalTypeEnum
    metadata: Dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    status: ProposalStatusEnum = ProposalStatusEnum.PROPOSAL_STATUS_UNSPECIFIED
    depends_on: List[UUID] = Field(default_factory=list)
    conflicts_with: List[UUID] = Field(default_factory=list)
    proposal_signature: Optional[str] = None
