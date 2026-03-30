"""Loaders и проверки конфигураций Step-A."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable, List, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator


_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_DIR = _ROOT / "config"


def _to_vector(values: Sequence[float], expected_len: int = 3) -> List[float]:
    if len(values) != expected_len:
        raise ValueError(f"Ожидалось {expected_len} компонентов, получено {len(values)}")
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Компоненты вектора должны быть конечными")
    return [float(v) for v in values]


def _vector_norm(vec: Sequence[float]) -> float:
    return math.sqrt(sum(component * component for component in vec))


def _cross(a: Sequence[float], b: Sequence[float]) -> List[float]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _matrix_rank(matrix: List[List[float]], eps: float = 1e-6) -> int:
    if not matrix or not matrix[0]:
        return 0

    rows = len(matrix)
    cols = len(matrix[0])
    rank = 0
    used_rows = set()

    for col in range(cols):
        pivot_row = None
        for row in range(rows):
            if row in used_rows:
                continue
            if abs(matrix[row][col]) > eps:
                pivot_row = row
                break
        if pivot_row is None:
            continue
        used_rows.add(pivot_row)
        pivot = matrix[pivot_row][col]
        for row in range(rows):
            if row == pivot_row:
                continue
            factor = matrix[row][col] / pivot
            if abs(factor) <= eps:
                continue
            for c in range(col, cols):
                matrix[row][c] -= factor * matrix[pivot_row][c]
        rank += 1
        if rank == rows:
            break
    return rank


class Vector3Model(BaseModel):
    """Простой 3D-вектор."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    x: float
    y: float
    z: float

    @classmethod
    def from_sequence(cls, values: Sequence[float]) -> "Vector3Model":
        converted = _to_vector(values, expected_len=3)
        return cls(x=converted[0], y=converted[1], z=converted[2])

    def as_list(self) -> List[float]:
        return [self.x, self.y, self.z]


class QuaternionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    x: float
    y: float
    z: float
    w: float

    @classmethod
    def from_sequence(cls, values: Sequence[float]) -> "QuaternionModel":
        converted = _to_vector(values, expected_len=4)
        return cls(x=converted[0], y=converted[1], z=converted[2], w=converted[3])


class ThrusterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    index: int
    cluster_id: str
    position_m: Vector3Model
    direction: Vector3Model
    f_max_newton: float = Field(ge=0.0)

    @field_validator("position_m", mode="before")
    @classmethod
    def _position_from_list(cls, value: Sequence[float] | Vector3Model) -> Vector3Model:
        if isinstance(value, Vector3Model):
            return value
        return Vector3Model.from_sequence(value)

    @field_validator("direction", mode="before")
    @classmethod
    def _direction_from_list(cls, value: Sequence[float] | Vector3Model) -> Vector3Model:
        if isinstance(value, Vector3Model):
            return value
        return Vector3Model.from_sequence(value)

    @field_validator("direction")
    @classmethod
    def _direction_normalized(cls, value: Vector3Model) -> Vector3Model:
        norm = _vector_norm(value.as_list())
        if norm < 1e-6:
            raise ValueError("Вектор направления thruster не может быть нулевым")
        if not 0.99 <= norm <= 1.01:
            raise ValueError("Вектор направления thruster должен быть нормирован")
        return value

    def force_vector(self) -> List[float]:
        direction = self.direction.as_list()
        return [component * self.f_max_newton for component in direction]

    def torque_vector(self) -> List[float]:
        position = self.position_m.as_list()
        direction = self.direction.as_list()
        return _cross(position, direction)


class HESSConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    p_avail_kw: float = Field(gt=0.0)
    p_peak_kw: float = Field(gt=0.0)
    pulse_window_s: float = Field(gt=0.0)
    recharge_window_s: float = Field(gt=0.0)
    soc_battery: dict
    soc_supercap: dict


class DockingPortPose(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    position: Vector3Model
    orientation_quat: QuaternionModel

    @field_validator("position", mode="before")
    @classmethod
    def _position(cls, value: Sequence[float] | Vector3Model) -> Vector3Model:
        if isinstance(value, Vector3Model):
            return value
        return Vector3Model.from_sequence(value)

    @field_validator("orientation_quat", mode="before")
    @classmethod
    def _orientation(cls, value: Sequence[float] | QuaternionModel) -> QuaternionModel:
        if isinstance(value, QuaternionModel):
            return value
        return QuaternionModel.from_sequence(value)


class DockingPortConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str
    pose_m: DockingPortPose
    capture_modes: List[str]
    bridge_profiles: List[str]
    hard_capture_force_kN: float = Field(gt=0.0)


class AntennaConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    pose_m: DockingPortPose
    azimuth_sector_deg: List[float]
    elevation_sector_deg: List[float]

    @field_validator("azimuth_sector_deg", "elevation_sector_deg")
    @classmethod
    def _sector(cls, value: Sequence[float]) -> List[float]:
        return _to_vector(value, expected_len=2)


class TransponderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    pose_m: DockingPortPose
    modes: List[str]
    default_mode: str


class AntennaXpdrConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    primary: AntennaConfig
    transponder: TransponderConfig


class SensorMountConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str
    position_m: Vector3Model
    normal: Vector3Model
    los_mask_asset: str

    @field_validator("position_m", "normal", mode="before")
    @classmethod
    def _vector(cls, value: Sequence[float] | Vector3Model) -> Vector3Model:
        if isinstance(value, Vector3Model):
            return value
        return Vector3Model.from_sequence(value)


def _load_json(path: Path) -> list | dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_thrusters_config(path: Path | None = None) -> List[ThrusterConfig]:
    target = path or (_CONFIG_DIR / "propulsion" / "thrusters.json")
    data = _load_json(target)
    return [ThrusterConfig.model_validate(item) for item in data]


def load_hess_config(path: Path | None = None) -> HESSConfig:
    target = path or (_CONFIG_DIR / "power" / "hess.json")
    data = _load_json(target)
    return HESSConfig.model_validate(data)


def load_docking_ports(path: Path | None = None) -> List[DockingPortConfig]:
    target = path or (_CONFIG_DIR / "docking" / "ports.json")
    data = _load_json(target)
    return [DockingPortConfig.model_validate(item) for item in data]


def load_antenna_config(path: Path | None = None) -> AntennaXpdrConfig:
    target = path or (_CONFIG_DIR / "comms" / "antenna.json")
    data = _load_json(target)
    return AntennaXpdrConfig.model_validate(data)


def load_sensor_mounts(path: Path | None = None) -> List[SensorMountConfig]:
    target = path or (_CONFIG_DIR / "sensors" / "mounts.json")
    data = _load_json(target)
    return [SensorMountConfig.model_validate(item) for item in data]


def build_thruster_allocation_matrix(thrusters: Iterable[ThrusterConfig]) -> List[List[float]]:
    thrusters_list = list(thrusters)
    if not thrusters_list:
        return [[0.0] * 0 for _ in range(6)]

    forces = [thruster.direction.as_list() for thruster in thrusters_list]
    torques = [thruster.torque_vector() for thruster in thrusters_list]

    matrix: List[List[float]] = []
    for axis in range(3):
        matrix.append([force[axis] for force in forces])
    for axis in range(3):
        matrix.append([torque[axis] for torque in torques])
    return matrix


def thruster_allocation_rank(thrusters: Iterable[ThrusterConfig]) -> int:
    matrix = build_thruster_allocation_matrix(thrusters)
    copied = [row[:] for row in matrix]
    return _matrix_rank(copied)
