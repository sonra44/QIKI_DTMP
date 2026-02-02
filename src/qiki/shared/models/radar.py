from __future__ import annotations

from datetime import datetime, UTC
from enum import IntEnum
from typing import List, Optional, Self
from uuid import UUID, uuid4

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ObjectTypeEnum(IntEnum):
    OBJECT_TYPE_UNSPECIFIED = 0
    DRONE = 1
    SHIP = 2
    STATION = 3
    ASTEROID = 4
    DEBRIS = 5


class FriendFoeEnum(IntEnum):
    FRIEND_FOE_UNSPECIFIED = 0
    FRIEND = 1
    FOE = 2
    UNKNOWN = 3


class TransponderModeEnum(IntEnum):
    OFF = 0
    ON = 1
    SILENT = 2
    SPOOF = 3


class RangeBand(IntEnum):
    RR_UNSPECIFIED = 0
    RR_LR = 1
    RR_SR = 2


class RadarTrackStatusEnum(IntEnum):
    # Keep numeric alignment with `protos/radar/v1/radar.proto` (no v2).
    UNSPECIFIED = 0
    NEW = 1
    TRACKED = 2
    LOST = 3
    COASTING = 4


class Vector3Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class RadarDetectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    range_m: float = Field(ge=0)
    bearing_deg: float
    elev_deg: float
    vr_mps: float
    snr_db: float = Field(ge=0)
    rcs_dbsm: float
    transponder_on: bool = False
    transponder_mode: TransponderModeEnum = TransponderModeEnum.OFF
    transponder_id: Optional[str] = None
    range_band: RangeBand = RangeBand.RR_UNSPECIFIED
    id_present: Optional[bool] = None

    @field_validator("bearing_deg")
    @classmethod
    def _bearing_range(cls, v: float) -> float:
        if not (0.0 <= v < 360.0):
            raise ValueError("bearing_deg must be in [0, 360)")
        return v

    @field_validator("elev_deg")
    @classmethod
    def _elev_range(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError("elev_deg must be in [-90, 90]")
        return v

    @model_validator(mode="after")
    def _validate_range_band(self) -> Self:
        if self.range_band == RangeBand.RR_LR:
            if self.transponder_id:
                raise ValueError("LR band must not carry transponder_id")
            if self.id_present:
                raise ValueError("LR band must not carry id_present")
        return self


class RadarFrameModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: int = 1
    frame_id: UUID = Field(default_factory=uuid4)
    sensor_id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # New (P0 trust): split times. `timestamp` is the legacy event time alias.
    ts_event: Optional[datetime] = None
    ts_ingest: Optional[datetime] = None
    detections: List[RadarDetectionModel] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize_frame_times(self) -> Self:
        # Backward compatibility: `timestamp` remains the canonical on-wire event time.
        if self.ts_event is None:
            self.ts_event = self.timestamp
        # Avoid dual sources of truth: keep them identical if both are present.
        if self.ts_event != self.timestamp:
            self.ts_event = self.timestamp
        return self


class RadarTrackModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: int = 1
    track_id: UUID = Field(default_factory=uuid4)
    object_type: ObjectTypeEnum = ObjectTypeEnum.OBJECT_TYPE_UNSPECIFIED
    iff: FriendFoeEnum = Field(
        default=FriendFoeEnum.UNKNOWN,
        validation_alias=AliasChoices("iff", "iff_class", "iffClass"),
    )
    transponder_on: bool = False
    transponder_mode: TransponderModeEnum = TransponderModeEnum.OFF
    transponder_id: Optional[str] = None
    quality: float = Field(ge=0.0, le=1.0, default=0.0)
    status: RadarTrackStatusEnum = RadarTrackStatusEnum.NEW

    range_m: float = Field(ge=0)
    bearing_deg: float
    elev_deg: float
    vr_mps: float
    snr_db: float = Field(ge=0)
    rcs_dbsm: float

    position: Optional[Vector3Model] = None
    velocity: Optional[Vector3Model] = None
    position_covariance: Optional[List[float]] = Field(
        default=None,
        validation_alias=AliasChoices(
            "position_covariance",
            "positionCovariance",
            "error_covariance",
            "errorCovariance",
        ),
    )
    velocity_covariance: Optional[List[float]] = None
    age_s: float = Field(ge=0.0, default=0.0)
    miss_count: int = Field(ge=0, default=0)

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # New (P0 trust): split times. `timestamp` is the legacy event time alias.
    ts_event: Optional[datetime] = None
    ts_ingest: Optional[datetime] = None
    range_band: RangeBand = RangeBand.RR_UNSPECIFIED
    id_present: Optional[bool] = None

    @field_validator("bearing_deg")
    @classmethod
    def _bearing_range(cls, v: float) -> float:
        if not (0.0 <= v < 360.0):
            raise ValueError("bearing_deg must be in [0, 360)")
        return v

    @field_validator("elev_deg")
    @classmethod
    def _elev_range(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError("elev_deg must be in [-90, 90]")
        return v

    @field_validator("position_covariance", "velocity_covariance")
    @classmethod
    def _covariance_length(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        if v is None:
            return v
        if len(v) != 6:
            raise ValueError(
                "covariance must contain exactly 6 elements (upper-triangle)"
            )
        return v

    @model_validator(mode="after")
    def _validate_lr_constraints(self) -> Self:
        if self.range_band == RangeBand.RR_LR:
            if self.transponder_id:
                raise ValueError("LR band must not carry transponder_id")
            if self.id_present:
                raise ValueError("LR band must not carry id_present")
            if self.transponder_mode not in (TransponderModeEnum.OFF,):
                raise ValueError("LR band must not carry transponder_mode")
        if self.ts_event is None:
            self.ts_event = self.timestamp
        if self.ts_event != self.timestamp:
            self.ts_event = self.timestamp
        return self
