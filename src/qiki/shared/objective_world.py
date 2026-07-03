from __future__ import annotations

"""Layer 06 objective-world truth contracts.

The objective world is the internal scene truth that exists before radar tracks,
sensor readings or operator targets.  A world object is not a radar track and a
radar track is not an operator objective.  Hidden truth may exist inside the
scene, but public mappings deliberately omit it unless a caller explicitly asks
for it.
"""

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Mapping, Sequence


OBJECTIVE_WORLD_SCHEMA_VERSION = 1


class WorldObjectType(StrEnum):
    UNKNOWN = "unknown"
    STATION = "station"
    DEBRIS = "debris"
    ASTEROID = "asteroid"
    DRONE = "drone"
    SHIP = "ship"
    FIELD = "field"


class WorldObjectStatus(StrEnum):
    ACTIVE = "active"
    DORMANT = "dormant"
    LOST = "lost"
    DESTROYED = "destroyed"
    UNKNOWN = "unknown"


class TransponderMode(StrEnum):
    OFF = "OFF"
    ON = "ON"
    SILENT = "SILENT"
    SPOOF = "SPOOF"


@dataclass(frozen=True, slots=True)
class WorldVector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @classmethod
    def from_value(cls, value: Sequence[float] | Mapping[str, Any] | None) -> "WorldVector3":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(_finite_float(value.get("x")), _finite_float(value.get("y")), _finite_float(value.get("z")))
        seq = list(value or [])
        return cls(
            _finite_float(seq[0] if len(seq) > 0 else 0.0),
            _finite_float(seq[1] if len(seq) > 1 else 0.0),
            _finite_float(seq[2] if len(seq) > 2 else 0.0),
        )

    def add_scaled(self, velocity: "WorldVector3", dt_s: float) -> "WorldVector3":
        dt = max(0.0, _finite_float(dt_s))
        return WorldVector3(
            self.x + velocity.x * dt,
            self.y + velocity.y * dt,
            self.z + velocity.z * dt,
        )

    def to_mapping(self) -> dict[str, float]:
        return {"x": float(self.x), "y": float(self.y), "z": float(self.z)}


@dataclass(frozen=True, slots=True)
class WorldObjectState:
    world_object_id: str
    object_type: WorldObjectType | str = WorldObjectType.UNKNOWN
    status: WorldObjectStatus | str = WorldObjectStatus.ACTIVE
    position_xyz_m: WorldVector3 | Mapping[str, Any] | Sequence[float] = field(default_factory=WorldVector3)
    velocity_xyz_m_s: WorldVector3 | Mapping[str, Any] | Sequence[float] = field(default_factory=WorldVector3)
    radius_m: float = 1.0
    collision_radius_m: float = 1.0
    radar_cross_section_dbsm: float = 0.0
    thermal_signature: Mapping[str, Any] = field(default_factory=dict)
    optical_signature: Mapping[str, Any] = field(default_factory=dict)
    comms_signature: Mapping[str, Any] = field(default_factory=dict)
    transponder_mode: str = "OFF"
    true_transponder_id: str | None = None
    visible_transponder_id: str | None = None
    hidden_truth: Mapping[str, Any] = field(default_factory=dict)
    observable_profile: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    evidence: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "world_object_id", str(self.world_object_id or "OBJ-UNKNOWN"))
        object.__setattr__(self, "object_type", _object_type(self.object_type))
        object.__setattr__(self, "status", _object_status(self.status))
        object.__setattr__(self, "position_xyz_m", WorldVector3.from_value(self.position_xyz_m))
        object.__setattr__(self, "velocity_xyz_m_s", WorldVector3.from_value(self.velocity_xyz_m_s))
        object.__setattr__(self, "radius_m", max(0.0, _finite_float(self.radius_m, 1.0)))
        object.__setattr__(self, "collision_radius_m", max(0.0, _finite_float(self.collision_radius_m, self.radius_m)))
        object.__setattr__(self, "radar_cross_section_dbsm", _finite_float(self.radar_cross_section_dbsm, 0.0))
        object.__setattr__(self, "thermal_signature", dict(self.thermal_signature or {}))
        object.__setattr__(self, "optical_signature", dict(self.optical_signature or {}))
        object.__setattr__(self, "comms_signature", dict(self.comms_signature or {}))
        object.__setattr__(self, "transponder_mode", _text(self.transponder_mode or "OFF").upper() or "OFF")
        object.__setattr__(self, "true_transponder_id", _str_or_none(self.true_transponder_id))
        object.__setattr__(self, "visible_transponder_id", _str_or_none(self.visible_transponder_id))
        object.__setattr__(self, "hidden_truth", dict(self.hidden_truth or {}))
        object.__setattr__(self, "observable_profile", dict(self.observable_profile or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))
        object.__setattr__(self, "evidence", tuple(str(item) for item in (self.evidence or ()) if str(item).strip()))

    @property
    def radar_visible(self) -> bool:
        return bool(dict(self.observable_profile or {}).get("radar_visible", True))

    def advance(self, delta_time_s: float) -> "WorldObjectState":
        position = self.position_xyz_m.add_scaled(self.velocity_xyz_m_s, delta_time_s)
        return replace(self, position_xyz_m=position)

    def to_mapping(self, *, include_hidden_truth: bool = False, include_hidden: bool = False) -> dict[str, Any]:
        include_hidden_truth = bool(include_hidden_truth or include_hidden)
        data: dict[str, Any] = {
            "world_object_id": self.world_object_id,
            "object_type": _object_type(self.object_type).value,
            "status": _object_status(self.status).value,
            "position_xyz_m": self.position_xyz_m.to_mapping(),
            "velocity_xyz_m_s": self.velocity_xyz_m_s.to_mapping(),
            "radius_m": float(self.radius_m),
            "collision_radius_m": float(self.collision_radius_m),
            "radar_cross_section_dbsm": float(self.radar_cross_section_dbsm),
            "thermal_signature": dict(self.thermal_signature or {}),
            "optical_signature": dict(self.optical_signature or {}),
            "comms_signature": dict(self.comms_signature or {}),
            "transponder_mode": self.transponder_mode,
            "visible_transponder_id": self.visible_transponder_id,
            "observable_profile": dict(self.observable_profile or {}),
            "metadata": dict(self.metadata or {}),
            "evidence": list(self.evidence),
        }
        if include_hidden_truth:
            data["true_transponder_id"] = self.true_transponder_id
            data["hidden_truth"] = dict(self.hidden_truth or {})
        return data

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WorldObjectState":
        return cls(
            world_object_id=str(data.get("world_object_id") or data.get("object_id") or "OBJ-UNKNOWN"),
            object_type=data.get("object_type", WorldObjectType.UNKNOWN),
            status=data.get("status", WorldObjectStatus.ACTIVE),
            position_xyz_m=data.get("position_xyz_m") or data.get("position") or {},
            velocity_xyz_m_s=data.get("velocity_xyz_m_s") or data.get("velocity") or {},
            radius_m=data.get("radius_m", 1.0),
            collision_radius_m=data.get("collision_radius_m", data.get("radius_m", 1.0)),
            radar_cross_section_dbsm=data.get("radar_cross_section_dbsm", data.get("rcs_dbsm", 0.0)),
            thermal_signature=dict(data.get("thermal_signature") or {}),
            optical_signature=dict(data.get("optical_signature") or {}),
            comms_signature=dict(data.get("comms_signature") or {}),
            transponder_mode=str(data.get("transponder_mode") or "OFF"),
            true_transponder_id=data.get("true_transponder_id"),
            visible_transponder_id=data.get("visible_transponder_id") or data.get("transponder_id"),
            hidden_truth=dict(data.get("hidden_truth") or {}),
            observable_profile=dict(data.get("observable_profile") or {}),
            metadata=dict(data.get("metadata") or {}),
            evidence=tuple(data.get("evidence") or ()),
        )


@dataclass(frozen=True, slots=True)
class ObjectiveWorldZone:
    zone_id: str
    zone_type: str
    center_xyz_m: WorldVector3 | Mapping[str, Any] | Sequence[float] = field(default_factory=WorldVector3)
    radius_m: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "zone_id", str(self.zone_id or "ZONE-UNKNOWN"))
        object.__setattr__(self, "zone_type", str(self.zone_type or "unknown"))
        object.__setattr__(self, "center_xyz_m", WorldVector3.from_value(self.center_xyz_m))
        object.__setattr__(self, "radius_m", max(0.0, _finite_float(self.radius_m)))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_type": self.zone_type,
            "center_xyz_m": self.center_xyz_m.to_mapping(),
            "radius_m": float(self.radius_m),
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True, slots=True)
class ObjectiveWorldField:
    field_id: str
    field_type: str
    value: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "field_id", str(self.field_id or "FIELD-UNKNOWN"))
        object.__setattr__(self, "field_type", str(self.field_type or "unknown"))
        object.__setattr__(self, "value", dict(self.value or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "field_type": self.field_type,
            "value": dict(self.value or {}),
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True, slots=True)
class ObjectiveWorldState:
    scene_id: str
    objects: tuple[WorldObjectState, ...] = field(default_factory=tuple)
    zones: tuple[ObjectiveWorldZone, ...] = field(default_factory=tuple)
    fields: tuple[ObjectiveWorldField, ...] = field(default_factory=tuple)
    world_tick_id: str | None = None
    world_snapshot_id: str | None = None
    source_world_snapshot_id: str | None = None
    sim_time_s: float | None = None
    source_path: str = "q_sim_service.WorldModel.objective_world"
    evidence: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = OBJECTIVE_WORLD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "scene_id", str(self.scene_id or "SCENE-UNKNOWN"))
        object.__setattr__(self, "objects", tuple(self.objects or ()))
        object.__setattr__(self, "zones", tuple(self.zones or ()))
        object.__setattr__(self, "fields", tuple(self.fields or ()))
        object.__setattr__(self, "source_world_snapshot_id", self.source_world_snapshot_id or self.world_snapshot_id)
        object.__setattr__(self, "sim_time_s", _finite_float_or_none(self.sim_time_s))
        object.__setattr__(self, "source_path", str(self.source_path or "q_sim_service.WorldModel.objective_world"))
        object.__setattr__(self, "evidence", tuple(str(item) for item in (self.evidence or ()) if str(item).strip()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def with_lineage(
        self,
        *,
        world_tick_id: str | None,
        world_snapshot_id: str | None,
        source_world_snapshot_id: str | None = None,
        sim_time_s: float | None,
    ) -> "ObjectiveWorldState":
        return replace(
            self,
            world_tick_id=world_tick_id,
            world_snapshot_id=world_snapshot_id,
            source_world_snapshot_id=source_world_snapshot_id or world_snapshot_id,
            sim_time_s=sim_time_s,
        )

    def object_by_id(self, world_object_id: str) -> WorldObjectState | None:
        wanted = str(world_object_id)
        for obj in self.objects:
            if obj.world_object_id == wanted:
                return obj
        return None

    def radar_visible_objects(self) -> tuple[WorldObjectState, ...]:
        return tuple(obj for obj in self.objects if obj.radar_visible and obj.status is WorldObjectStatus.ACTIVE)

    def advance(self, delta_time_s: float) -> "ObjectiveWorldState":
        return replace(self, objects=tuple(obj.advance(delta_time_s) for obj in self.objects))

    def to_mapping(self, *, include_hidden_truth: bool = False, include_hidden: bool = False) -> dict[str, Any]:
        include_hidden_truth = bool(include_hidden_truth or include_hidden)
        out = {
            "schema_version": int(self.schema_version),
            "scene_id": self.scene_id,
            "world_tick_id": self.world_tick_id,
            "world_snapshot_id": self.world_snapshot_id,
            "source_world_snapshot_id": self.source_world_snapshot_id or self.world_snapshot_id,
            "sim_time_s": self.sim_time_s,
            "source_path": self.source_path,
            "objects": [obj.to_mapping(include_hidden_truth=include_hidden_truth) for obj in self.objects],
            "zones": [zone.to_mapping() for zone in self.zones],
            "fields": [field_item.to_mapping() for field_item in self.fields],
            "evidence": list(self.evidence),
            "metadata": dict(self.metadata or {}),
        }
        meta = dict(self.metadata or {})
        if isinstance(meta.get("proximity"), Mapping):
            out["proximity"] = dict(meta["proximity"])
        return out



def _object_type(value: Any) -> WorldObjectType:
    if isinstance(value, WorldObjectType):
        return value
    text = str(value or "").strip().lower()
    for item in WorldObjectType:
        if text in {item.value, item.name.lower()}:
            return item
    return WorldObjectType.UNKNOWN



def _object_status(value: Any) -> WorldObjectStatus:
    if isinstance(value, WorldObjectStatus):
        return value
    text = str(value or "").strip().lower()
    for item in WorldObjectStatus:
        if text in {item.value, item.name.lower()}:
            return item
    return WorldObjectStatus.UNKNOWN



def _finite_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(default)
    try:
        parsed = float(value)
    except Exception:
        return float(default)
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return float(default)
    return float(parsed)



def _finite_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    parsed = _finite_float(value, float("nan"))
    if parsed != parsed:
        return None
    return float(parsed)



def _text(value: Any) -> str:
    return str(value or "").strip()



def _str_or_none(value: Any) -> str | None:
    text = _text(value)
    return text or None


def vector3_mapping(value: Sequence[float] | Mapping[str, Any] | WorldVector3 | None) -> dict[str, float]:
    return WorldVector3.from_value(value).to_mapping()


def vector3_sub(a: Sequence[float] | Mapping[str, Any] | WorldVector3 | None, b: Sequence[float] | Mapping[str, Any] | WorldVector3 | None) -> dict[str, float]:
    av = WorldVector3.from_value(a)
    bv = WorldVector3.from_value(b)
    return {"x": av.x - bv.x, "y": av.y - bv.y, "z": av.z - bv.z}


def vector3_norm(value: Sequence[float] | Mapping[str, Any] | WorldVector3 | None) -> float:
    v = WorldVector3.from_value(value)
    return (v.x * v.x + v.y * v.y + v.z * v.z) ** 0.5


__all__ = [
    "OBJECTIVE_WORLD_SCHEMA_VERSION",
    "ObjectiveWorldField",
    "ObjectiveWorldState",
    "ObjectiveWorldZone",
    "WorldObjectState",
    "WorldObjectStatus",
    "WorldObjectType",
    "WorldVector3",
    "TransponderMode",
    "vector3_mapping",
    "vector3_sub",
    "vector3_norm",
]
