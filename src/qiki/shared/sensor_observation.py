from __future__ import annotations

"""Layer-07 sensor-observation boundary contracts.

A sensor observation is the explicit boundary between objective-world truth and
runtime sensor readings. It is not a radar track, not an operator target and not
private objective truth. It records what a concrete sensor could observe from an
ObjectiveWorldState and carries the same world snapshot lineage as the scene it
observed.
"""

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence

from qiki.shared.objective_world import ObjectiveWorldState, vector3_mapping, vector3_norm, vector3_sub


SENSOR_OBSERVATION_SCHEMA_VERSION = 1


class SensorObservationKind(StrEnum):
    UNKNOWN = "unknown"
    PROXIMITY = "proximity"
    RADAR = "radar"
    OPTICAL = "optical"
    THERMAL = "thermal"


class SensorObservationStatus(StrEnum):
    OBSERVED = "observed"
    CLEAR = "clear"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ObservedObjectSnapshot:
    """Public sensor-facing observation of one objective-world object."""

    world_object_id: str
    object_type: str = "unknown"
    object_status: str = "unknown"
    range_m: float | None = None
    relative_position_xyz_m: Mapping[str, float] = field(default_factory=dict)
    relative_velocity_xyz_m_s: Mapping[str, float] = field(default_factory=dict)
    collision_radius_m: float | None = None
    observable: bool = True
    confidence: float | None = None
    source_path: str = "ObjectiveWorldState.objects"
    evidence: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "world_object_id", str(self.world_object_id or "OBJ-UNKNOWN"))
        object.__setattr__(self, "object_type", str(self.object_type or "unknown"))
        object.__setattr__(self, "object_status", str(self.object_status or "unknown"))
        object.__setattr__(self, "range_m", _finite_float_or_none(self.range_m))
        object.__setattr__(self, "relative_position_xyz_m", vector3_mapping(self.relative_position_xyz_m))
        object.__setattr__(self, "relative_velocity_xyz_m_s", vector3_mapping(self.relative_velocity_xyz_m_s))
        object.__setattr__(self, "collision_radius_m", _finite_float_or_none(self.collision_radius_m))
        object.__setattr__(self, "observable", bool(self.observable))
        object.__setattr__(self, "confidence", _clamp01_or_none(self.confidence))
        object.__setattr__(self, "source_path", str(self.source_path or "ObjectiveWorldState.objects"))
        object.__setattr__(self, "evidence", tuple(str(item) for item in (self.evidence or ()) if str(item).strip()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "world_object_id": self.world_object_id,
            "object_type": self.object_type,
            "object_status": self.object_status,
            "range_m": self.range_m,
            "relative_position_xyz_m": dict(self.relative_position_xyz_m),
            "relative_velocity_xyz_m_s": dict(self.relative_velocity_xyz_m_s),
            "collision_radius_m": self.collision_radius_m,
            "observable": self.observable,
            "confidence": self.confidence,
            "source_path": self.source_path,
            "evidence": list(self.evidence),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ObservedObjectSnapshot":
        return cls(
            world_object_id=str(data.get("world_object_id") or data.get("object_id") or "OBJ-UNKNOWN"),
            object_type=str(data.get("object_type") or "unknown"),
            object_status=str(data.get("object_status") or data.get("status") or "unknown"),
            range_m=data.get("range_m"),
            relative_position_xyz_m=data.get("relative_position_xyz_m") or data.get("relative_position") or {},
            relative_velocity_xyz_m_s=data.get("relative_velocity_xyz_m_s") or data.get("relative_velocity") or {},
            collision_radius_m=data.get("collision_radius_m"),
            observable=bool(data.get("observable", True)),
            confidence=data.get("confidence"),
            source_path=str(data.get("source_path") or "ObjectiveWorldState.objects"),
            evidence=tuple(data.get("evidence") or ()),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class SensorObservationSnapshot:
    """Canonical boundary from lower-truth scene to sensor-specific observation."""

    observation_id: str
    sensor_id: str
    sensor_type: str
    observation_kind: SensorObservationKind | str
    status: SensorObservationStatus | str
    source_path: str
    source_kind: str = "DERIVED"
    objective_scene_id: str | None = None
    observed_objects: tuple[ObservedObjectSnapshot, ...] = field(default_factory=tuple)
    nearest_world_object_id: str | None = None
    min_range_m: float | None = None
    contacts_count: int = 0
    collision_envelope: bool = False
    confidence: float | None = None
    world_tick_id: str | None = None
    world_snapshot_id: str | None = None
    source_world_snapshot_id: str | None = None
    sim_time_s: float | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = SENSOR_OBSERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_id", str(self.observation_id or "OBS-UNKNOWN"))
        object.__setattr__(self, "sensor_id", str(self.sensor_id or "sensor_unknown"))
        object.__setattr__(self, "sensor_type", str(self.sensor_type or "unknown"))
        object.__setattr__(self, "observation_kind", _observation_kind(self.observation_kind))
        object.__setattr__(self, "status", _observation_status(self.status))
        object.__setattr__(self, "source_path", str(self.source_path or "SensorObservationSnapshot"))
        object.__setattr__(self, "source_kind", str(self.source_kind or "DERIVED").upper())
        object.__setattr__(self, "objective_scene_id", _str_or_none(self.objective_scene_id))
        object.__setattr__(self, "observed_objects", tuple(self.observed_objects or ()))
        object.__setattr__(self, "nearest_world_object_id", _str_or_none(self.nearest_world_object_id))
        object.__setattr__(self, "min_range_m", _finite_float_or_none(self.min_range_m))
        object.__setattr__(self, "contacts_count", max(0, _int(self.contacts_count)))
        object.__setattr__(self, "collision_envelope", bool(self.collision_envelope))
        object.__setattr__(self, "confidence", _clamp01_or_none(self.confidence))
        object.__setattr__(self, "world_tick_id", _str_or_none(self.world_tick_id))
        object.__setattr__(self, "world_snapshot_id", _str_or_none(self.world_snapshot_id))
        object.__setattr__(self, "source_world_snapshot_id", _str_or_none(self.source_world_snapshot_id) or _str_or_none(self.world_snapshot_id))
        object.__setattr__(self, "sim_time_s", _finite_float_or_none(self.sim_time_s))
        object.__setattr__(self, "evidence", tuple(str(item) for item in (self.evidence or ()) if str(item).strip()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))
        object.__setattr__(self, "schema_version", max(1, _int(self.schema_version, SENSOR_OBSERVATION_SCHEMA_VERSION)))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "observation_id": self.observation_id,
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "observation_kind": self.observation_kind.value,
            "status": self.status.value,
            "source_kind": self.source_kind,
            "source_path": self.source_path,
            "objective_scene_id": self.objective_scene_id,
            "observed_objects": [item.to_mapping() for item in self.observed_objects],
            "nearest_world_object_id": self.nearest_world_object_id,
            "min_range_m": self.min_range_m,
            "contacts_count": int(self.contacts_count),
            "contacts": int(self.contacts_count),
            "collision_envelope": bool(self.collision_envelope),
            "confidence": self.confidence,
            "world_tick_id": self.world_tick_id,
            "world_snapshot_id": self.world_snapshot_id,
            "source_world_snapshot_id": self.source_world_snapshot_id or self.world_snapshot_id,
            "sim_time_s": self.sim_time_s,
            "evidence": list(self.evidence),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SensorObservationSnapshot":
        raw_objects = data.get("observed_objects") or data.get("objects") or ()
        objects: list[ObservedObjectSnapshot] = []
        if isinstance(raw_objects, Sequence) and not isinstance(raw_objects, (str, bytes)):
            for item in raw_objects:
                if isinstance(item, ObservedObjectSnapshot):
                    objects.append(item)
                elif isinstance(item, Mapping):
                    objects.append(ObservedObjectSnapshot.from_mapping(item))
        return cls(
            observation_id=str(data.get("observation_id") or "OBS-UNKNOWN"),
            sensor_id=str(data.get("sensor_id") or "sensor_unknown"),
            sensor_type=str(data.get("sensor_type") or "unknown"),
            observation_kind=data.get("observation_kind") or data.get("kind") or SensorObservationKind.UNKNOWN,
            status=data.get("status") or SensorObservationStatus.UNKNOWN,
            source_kind=str(data.get("source_kind") or "DERIVED"),
            source_path=str(data.get("source_path") or "SensorObservationSnapshot"),
            objective_scene_id=data.get("objective_scene_id") or data.get("scene_id"),
            observed_objects=tuple(objects),
            nearest_world_object_id=data.get("nearest_world_object_id") or data.get("nearest_object_id"),
            min_range_m=data.get("min_range_m"),
            contacts_count=data.get("contacts_count", data.get("contacts", len(objects))),
            collision_envelope=bool(data.get("collision_envelope", False)),
            confidence=data.get("confidence"),
            world_tick_id=data.get("world_tick_id"),
            world_snapshot_id=data.get("world_snapshot_id"),
            source_world_snapshot_id=data.get("source_world_snapshot_id") or data.get("world_snapshot_id"),
            sim_time_s=data.get("sim_time_s"),
            evidence=tuple(data.get("evidence") or ()),
            metadata=dict(data.get("metadata") or {}),
            schema_version=data.get("schema_version", SENSOR_OBSERVATION_SCHEMA_VERSION),
        )

    def to_sensor_value(self) -> dict[str, Any]:
        return {
            "contacts": int(self.contacts_count),
            "contacts_count": int(self.contacts_count),
            "min_range_m": self.min_range_m,
            "nearest_world_object_id": self.nearest_world_object_id,
            "collision_envelope": bool(self.collision_envelope),
            "observed_world_object_ids": [item.world_object_id for item in self.observed_objects],
            "observation_id": self.observation_id,
            "objective_scene_id": self.objective_scene_id,
        }


@dataclass(frozen=True, slots=True)
class SensorObservationFrame:
    """A small frame grouping sensor observations over one objective-world snapshot."""

    observation_frame_id: str
    observations: tuple[SensorObservationSnapshot, ...] = field(default_factory=tuple)
    generated_at_epoch_s: float | None = None
    source_path: str = "SensorObservationFrame"
    objective_scene_id: str | None = None
    world_tick_id: str | None = None
    world_snapshot_id: str | None = None
    source_world_snapshot_id: str | None = None
    sim_time_s: float | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = SENSOR_OBSERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        observations: list[SensorObservationSnapshot] = []
        for item in self.observations or ():
            if isinstance(item, SensorObservationSnapshot):
                observations.append(item)
            elif isinstance(item, Mapping):
                observations.append(SensorObservationSnapshot.from_mapping(item))
        object.__setattr__(self, "observation_frame_id", str(self.observation_frame_id or "SOF-UNKNOWN"))
        object.__setattr__(self, "observations", tuple(observations))
        object.__setattr__(self, "generated_at_epoch_s", _finite_float_or_none(self.generated_at_epoch_s))
        object.__setattr__(self, "source_path", str(self.source_path or "SensorObservationFrame"))
        object.__setattr__(self, "objective_scene_id", _str_or_none(self.objective_scene_id))
        object.__setattr__(self, "world_tick_id", _str_or_none(self.world_tick_id))
        object.__setattr__(self, "world_snapshot_id", _str_or_none(self.world_snapshot_id))
        object.__setattr__(self, "source_world_snapshot_id", _str_or_none(self.source_world_snapshot_id) or _str_or_none(self.world_snapshot_id))
        object.__setattr__(self, "sim_time_s", _finite_float_or_none(self.sim_time_s))
        object.__setattr__(self, "evidence", tuple(str(item) for item in (self.evidence or ()) if str(item).strip()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))
        object.__setattr__(self, "schema_version", max(1, _int(self.schema_version, SENSOR_OBSERVATION_SCHEMA_VERSION)))

    def by_sensor_id(self, sensor_id: str) -> SensorObservationSnapshot | None:
        wanted = str(sensor_id)
        for item in self.observations:
            if item.sensor_id == wanted:
                return item
        return None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "observation_frame_id": self.observation_frame_id,
            "generated_at_epoch_s": self.generated_at_epoch_s,
            "source_path": self.source_path,
            "objective_scene_id": self.objective_scene_id,
            "world_tick_id": self.world_tick_id,
            "world_snapshot_id": self.world_snapshot_id,
            "source_world_snapshot_id": self.source_world_snapshot_id or self.world_snapshot_id,
            "sim_time_s": self.sim_time_s,
            "observations": [item.to_mapping() for item in self.observations],
            "evidence": list(self.evidence),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SensorObservationFrame":
        raw = data.get("observations") or ()
        observations: list[SensorObservationSnapshot] = []
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            for item in raw:
                if isinstance(item, SensorObservationSnapshot):
                    observations.append(item)
                elif isinstance(item, Mapping):
                    observations.append(SensorObservationSnapshot.from_mapping(item))
        return cls(
            observation_frame_id=str(data.get("observation_frame_id") or "SOF-UNKNOWN"),
            observations=tuple(observations),
            generated_at_epoch_s=data.get("generated_at_epoch_s"),
            source_path=str(data.get("source_path") or "SensorObservationFrame"),
            objective_scene_id=data.get("objective_scene_id"),
            world_tick_id=data.get("world_tick_id"),
            world_snapshot_id=data.get("world_snapshot_id"),
            source_world_snapshot_id=data.get("source_world_snapshot_id") or data.get("world_snapshot_id"),
            sim_time_s=data.get("sim_time_s"),
            evidence=tuple(data.get("evidence") or ()),
            metadata=dict(data.get("metadata") or {}),
            schema_version=data.get("schema_version", SENSOR_OBSERVATION_SCHEMA_VERSION),
        )


def build_sensor_observation_frame_from_objective_world(
    scene: ObjectiveWorldState | Mapping[str, Any],
    *,
    observer_position_xyz_m: Mapping[str, Any] | Sequence[float],
    observer_velocity_xyz_m_s: Mapping[str, Any] | Sequence[float] | None = None,
    generated_at_epoch_s: float | None = None,
    proximity_sensor_id: str = "sensor_proximity",
    collision_threshold_m: float = 50.0,
) -> SensorObservationFrame:
    """Build one Layer-07 observation frame over a public ObjectiveWorldState."""

    scene_map = _scene_to_public_mapping(scene)
    scene_id = _str_or_none(scene_map.get("scene_id"))
    world_tick_id = _str_or_none(scene_map.get("world_tick_id"))
    world_snapshot_id = _str_or_none(scene_map.get("world_snapshot_id"))
    source_world_snapshot_id = _str_or_none(scene_map.get("source_world_snapshot_id")) or world_snapshot_id
    sim_time_s = _finite_float_or_none(scene_map.get("sim_time_s"))
    observation = build_proximity_observation_from_objective_world(
        scene_map,
        observer_position_xyz_m=observer_position_xyz_m,
        observer_velocity_xyz_m_s=observer_velocity_xyz_m_s,
        sensor_id=proximity_sensor_id,
        collision_threshold_m=collision_threshold_m,
    )
    frame_id = f"SOF-{world_snapshot_id}" if world_snapshot_id else _format_observation_id(
        sensor_id="sensor_observation_frame",
        world_snapshot_id=None,
        fallback_scene_id=scene_id,
    )
    return SensorObservationFrame(
        observation_frame_id=frame_id,
        observations=(observation,),
        generated_at_epoch_s=generated_at_epoch_s,
        source_path="ObjectiveWorldState->SensorObservationFrame",
        objective_scene_id=scene_id,
        world_tick_id=world_tick_id,
        world_snapshot_id=world_snapshot_id,
        source_world_snapshot_id=source_world_snapshot_id,
        sim_time_s=sim_time_s,
        evidence=(
            "layer=07.sensor_observation",
            "observation_over=ObjectiveWorldState",
            "private_truth_redacted=true",
        ),
        metadata={
            "observation_count": 1,
            "source_object_count": len(_iter_public_objects(scene_map)),
        },
    )


def build_proximity_observation_from_objective_world(
    scene: ObjectiveWorldState | Mapping[str, Any],
    *,
    observer_position_xyz_m: Mapping[str, Any] | Sequence[float],
    observer_velocity_xyz_m_s: Mapping[str, Any] | Sequence[float] | None = None,
    sensor_id: str = "sensor_proximity",
    collision_threshold_m: float = 50.0,
) -> SensorObservationSnapshot:
    """Build a truthful proximity observation over ObjectiveWorldState.

    This function does not distort or invent readings. It creates the explicit
    intermediate observation that sensor_runtime can package as a sensor reading.
    Hidden objective-world truth is intentionally ignored.
    """

    scene_map = _scene_to_public_mapping(scene)
    scene_id = _str_or_none(scene_map.get("scene_id"))
    world_tick_id = _str_or_none(scene_map.get("world_tick_id"))
    world_snapshot_id = _str_or_none(scene_map.get("world_snapshot_id"))
    source_world_snapshot_id = _str_or_none(scene_map.get("source_world_snapshot_id")) or world_snapshot_id
    sim_time_s = _finite_float_or_none(scene_map.get("sim_time_s"))
    observer_position = vector3_mapping(observer_position_xyz_m)
    observer_velocity = vector3_mapping(observer_velocity_xyz_m_s or {})
    collision_threshold = max(0.0, _finite_float(collision_threshold_m, 50.0))

    public_objects = _iter_public_objects(scene_map)
    objects: list[ObservedObjectSnapshot] = []
    for obj in public_objects:
        profile = obj.get("observable_profile") if isinstance(obj.get("observable_profile"), Mapping) else {}
        if profile.get("proximity_visible") is False:
            continue
        obj_status = str(obj.get("status") or "unknown").strip().lower()
        if obj_status not in {"active", "dormant"}:
            continue
        world_object_id = str(obj.get("world_object_id") or "").strip()
        if not world_object_id:
            continue
        pos = obj.get("position_xyz_m") if isinstance(obj.get("position_xyz_m"), Mapping) else {}
        vel = obj.get("velocity_xyz_m_s") if isinstance(obj.get("velocity_xyz_m_s"), Mapping) else {}
        rel_pos = vector3_sub(pos, observer_position)
        rel_vel = vector3_sub(vel, observer_velocity)
        range_m = vector3_norm(rel_pos)
        confidence = _object_observation_confidence(range_m=range_m, profile=profile)
        objects.append(
            ObservedObjectSnapshot(
                world_object_id=world_object_id,
                object_type=str(obj.get("object_type") or "unknown"),
                object_status=obj_status,
                range_m=range_m,
                relative_position_xyz_m=rel_pos,
                relative_velocity_xyz_m_s=rel_vel,
                collision_radius_m=obj.get("collision_radius_m"),
                observable=True,
                confidence=confidence,
                source_path=f"ObjectiveWorldState.objects[{world_object_id}]",
                evidence=(
                    "source=objective_world",
                    "private_truth_redacted=true",
                    f"world_snapshot_id={world_snapshot_id}" if world_snapshot_id else "world_snapshot_id=missing",
                ),
                metadata={"objective_scene_id": scene_id},
            )
        )
    objects.sort(key=lambda item: (float("inf") if item.range_m is None else float(item.range_m), item.world_object_id))

    nearest = objects[0] if objects else None
    status = SensorObservationStatus.OBSERVED if nearest is not None else SensorObservationStatus.CLEAR
    confidence = 0.82 if nearest is not None else 0.7
    if world_snapshot_id is None:
        status = SensorObservationStatus.DEGRADED if nearest is not None else SensorObservationStatus.UNKNOWN
        confidence = min(confidence, 0.35)
    observation_id = _format_observation_id(sensor_id=sensor_id, world_snapshot_id=world_snapshot_id, fallback_scene_id=scene_id)
    return SensorObservationSnapshot(
        observation_id=observation_id,
        sensor_id=sensor_id,
        sensor_type="proximity",
        observation_kind=SensorObservationKind.PROXIMITY,
        status=status,
        source_kind="DERIVED",
        source_path=f"SensorObservationSnapshot[{observation_id}]",
        objective_scene_id=scene_id,
        observed_objects=tuple(objects),
        nearest_world_object_id=nearest.world_object_id if nearest is not None else None,
        min_range_m=nearest.range_m if nearest is not None else None,
        contacts_count=len(objects),
        collision_envelope=bool(nearest is not None and nearest.range_m is not None and nearest.range_m <= collision_threshold),
        confidence=confidence,
        world_tick_id=world_tick_id,
        world_snapshot_id=world_snapshot_id,
        source_world_snapshot_id=source_world_snapshot_id,
        sim_time_s=sim_time_s,
        evidence=(
            "layer=07.sensor_observation",
            "observation_over=ObjectiveWorldState",
            "truth_not_mutated=true",
            "private_truth_redacted=true",
        ),
        metadata={
            "source_object_count": len(public_objects),
            "collision_threshold_m": collision_threshold,
        },
    )


def _scene_to_public_mapping(scene: ObjectiveWorldState | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(scene, ObjectiveWorldState):
        return scene.to_mapping(include_hidden_truth=False)
    if isinstance(scene, Mapping):
        out = dict(scene)
        raw = out.get("objects")
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            public_objects: list[dict[str, Any]] = []
            for item in raw:
                if not isinstance(item, Mapping):
                    continue
                obj = dict(item)
                obj.pop("hidden_truth", None)
                obj.pop("true_transponder_id", None)
                public_objects.append(obj)
            out["objects"] = public_objects
        return out
    return {}


def _iter_public_objects(scene_map: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = scene_map.get("objects") if isinstance(scene_map, Mapping) else []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _object_observation_confidence(*, range_m: float, profile: Mapping[str, Any]) -> float:
    base = _finite_float(profile.get("proximity_confidence"), 0.82) if isinstance(profile, Mapping) else 0.82
    if range_m > 50000.0:
        base *= 0.5
    elif range_m > 10000.0:
        base *= 0.75
    return max(0.0, min(1.0, base))


def _format_observation_id(*, sensor_id: str, world_snapshot_id: str | None, fallback_scene_id: str | None) -> str:
    suffix = str(world_snapshot_id or fallback_scene_id or "NO-SNAPSHOT").replace(" ", "-")
    clean_sensor = str(sensor_id or "sensor_unknown").replace(" ", "-")
    return f"OBS-{clean_sensor}-{suffix}"


def _observation_kind(value: SensorObservationKind | str | None) -> SensorObservationKind:
    if isinstance(value, SensorObservationKind):
        return value
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    for item in SensorObservationKind:
        if text in {item.value, item.name.lower()}:
            return item
    return SensorObservationKind.UNKNOWN


def _observation_status(value: SensorObservationStatus | str | None) -> SensorObservationStatus:
    if isinstance(value, SensorObservationStatus):
        return value
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "ok": SensorObservationStatus.OBSERVED,
        "detected": SensorObservationStatus.OBSERVED,
        "observed": SensorObservationStatus.OBSERVED,
        "clear": SensorObservationStatus.CLEAR,
        "empty": SensorObservationStatus.CLEAR,
        "none": SensorObservationStatus.CLEAR,
        "degraded": SensorObservationStatus.DEGRADED,
        "blocked": SensorObservationStatus.BLOCKED,
        "missing": SensorObservationStatus.MISSING,
        "unknown": SensorObservationStatus.UNKNOWN,
    }
    return aliases.get(text, SensorObservationStatus.UNKNOWN)


def _finite_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(default)
    try:
        parsed = float(value)
    except Exception:
        return float(default)
    return parsed if math.isfinite(parsed) else float(default)


def _finite_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    parsed = _finite_float(value, float("nan"))
    if parsed != parsed:
        return None
    return float(parsed)


def _clamp01_or_none(value: Any) -> float | None:
    parsed = _finite_float_or_none(value)
    if parsed is None:
        return None
    return max(0.0, min(1.0, parsed))


def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _str_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


__all__ = [
    "SENSOR_OBSERVATION_SCHEMA_VERSION",
    "ObservedObjectSnapshot",
    "SensorObservationFrame",
    "SensorObservationKind",
    "SensorObservationSnapshot",
    "SensorObservationStatus",
    "build_proximity_observation_from_objective_world",
    "build_sensor_observation_frame_from_objective_world",
]
