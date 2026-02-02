from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Position3D(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float


class AttitudeTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Radians, right-handed frame (x forward, y left, z up).
    roll_rad: float = Field(ge=-6.283185307179586, le=6.283185307179586)
    pitch_rad: float = Field(ge=-6.283185307179586, le=6.283185307179586)
    yaw_rad: float = Field(ge=-6.283185307179586, le=6.283185307179586)


class HullTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    integrity: float = Field(ge=0.0, le=100.0)


class PowerTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    soc_pct: float = Field(ge=0.0, le=100.0)
    # Operator-facing diagnostics: breakdown of sources/loads, not additional sources of truth.
    sources_w: dict[str, float] = Field(default_factory=dict)
    loads_w: dict[str, float] = Field(default_factory=dict)
    power_in_w: float = Field(ge=0.0)
    power_out_w: float = Field(ge=0.0)
    bus_v: float = Field(ge=0.0)
    bus_a: float = Field(ge=0.0)
    # Power Supervisor state (virtual hardware, no-mocks).
    load_shedding: bool = Field(default=False)
    shed_loads: list[str] = Field(default_factory=list)
    shed_reasons: list[str] = Field(default_factory=list)

    # PDU (power path constraints) - virtual hardware.
    pdu_limit_w: float = Field(default=0.0, ge=0.0)
    pdu_throttled: bool = Field(default=False)
    throttled_loads: list[str] = Field(default_factory=list)

    # Faults and peak buffer (supercaps).
    faults: list[str] = Field(default_factory=list)
    supercap_soc_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    supercap_charge_w: float = Field(default=0.0, ge=0.0)
    supercap_discharge_w: float = Field(default=0.0, ge=0.0)

    # Dock Power Bridge.
    dock_connected: bool = Field(default=False)
    dock_soft_start_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    dock_power_w: float = Field(default=0.0, ge=0.0)
    dock_v: float = Field(default=0.0, ge=0.0)
    dock_a: float = Field(default=0.0, ge=0.0)
    dock_temp_c: float = Field(default=0.0)

    # NBL Power Budgeter.
    nbl_active: bool = Field(default=False)
    nbl_allowed: bool = Field(default=False)
    nbl_power_w: float = Field(default=0.0, ge=0.0)
    nbl_budget_w: float = Field(default=0.0, ge=0.0)


class ThermalNodeTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    temp_c: float


class ThermalTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[ThermalNodeTelemetry]


class TelemetrySnapshotModel(BaseModel):
    """Telemetry snapshot published to `qiki.telemetry`.

    Contract goals:
    - `position` is always 3D (x,y,z required).
    - timestamp is provided as both RFC3339 string and unix ms for easy UI freshness checks.
    - extra keys are allowed for forward compatibility, but core keys are strict.
    """

    model_config = ConfigDict(extra="allow")

    schema_version: int = Field(default=1, ge=1)
    source: str
    timestamp: str
    ts_unix_ms: int = Field(ge=0)

    position: Position3D
    velocity: float
    heading: float
    attitude: AttitudeTelemetry
    battery: float

    hull: HullTelemetry
    power: PowerTelemetry
    thermal: ThermalTelemetry
    radiation_usvh: float
    temp_external_c: float
    temp_core_c: float
    cpu_usage: float | None = Field(default=None, ge=0.0, le=100.0)
    memory_usage: float | None = Field(default=None, ge=0.0, le=100.0)

    @field_validator("source", "timestamp")
    @classmethod
    def _non_empty_str(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("must be a non-empty string")
        return v

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, v: int) -> int:
        if v != 1:
            raise ValueError("unsupported schema_version")
        return v

    @classmethod
    def normalize_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate and return a normalized JSON-ready dict."""

        model = cls.model_validate(payload)
        return model.model_dump(mode="json")
