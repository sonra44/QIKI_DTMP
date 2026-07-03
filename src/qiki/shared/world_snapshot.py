from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class WorldSnapshotSource(StrEnum):
    """Known producers/consumers that can stamp world-truth lineage."""

    INIT = "init"
    TICK = "tick"
    MUTATION = "mutation"
    READ = "read"
    TELEMETRY = "telemetry"
    SENSOR_RUNTIME = "sensor_runtime"
    SENSOR_OBSERVATION = "sensor_observation"
    SENSOR_TRUST = "sensor_trust"
    RADAR = "radar"
    OBJECTIVE_WORLD = "objective_world"
    EVENT = "event"


_WORLD_ID_WIDTH = 12


def format_world_tick_id(index: int | str | None) -> str:
    """Return the canonical textual tick id used by runtime payloads."""

    return f"WT-{_non_negative_int(index):0{_WORLD_ID_WIDTH}d}"


def format_world_snapshot_id(index: int | str | None) -> str:
    """Return the canonical textual snapshot id used by runtime payloads."""

    return f"WM-{_non_negative_int(index):0{_WORLD_ID_WIDTH}d}"


@dataclass(frozen=True, slots=True)
class WorldSnapshotRef:
    """Protobuf-free reference to a concrete WorldModel state.

    This is not a copy of the whole world.  It is the lineage marker carried by
    telemetry, sensor runtime, radar and event payloads so operator/evidence
    layers can prove which lower-truth snapshot a fact came from.
    """

    world_tick_index: int = 0
    world_snapshot_index: int = 0
    sim_time_s: float = 0.0
    source: WorldSnapshotSource | str = WorldSnapshotSource.READ
    source_path: str = "q_sim_service.WorldModel"
    reason: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "world_tick_index", _non_negative_int(self.world_tick_index))
        object.__setattr__(self, "world_snapshot_index", _non_negative_int(self.world_snapshot_index))
        object.__setattr__(self, "sim_time_s", _finite_float(self.sim_time_s))
        object.__setattr__(self, "source", normalize_world_snapshot_source(self.source))
        object.__setattr__(self, "source_path", str(self.source_path or "q_sim_service.WorldModel"))
        object.__setattr__(self, "reason", str(self.reason or ""))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def world_tick_id(self) -> str:
        return format_world_tick_id(self.world_tick_index)

    @property
    def world_snapshot_id(self) -> str:
        return format_world_snapshot_id(self.world_snapshot_index)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "world_tick_index": self.world_tick_index,
            "world_tick_id": self.world_tick_id,
            "world_snapshot_index": self.world_snapshot_index,
            "world_snapshot_id": self.world_snapshot_id,
            "sim_time_s": self.sim_time_s,
            "source": self.source.value,
            "source_path": self.source_path,
            "reason": self.reason,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> WorldSnapshotRef:
        if not isinstance(data, Mapping):
            return cls()
        tick_index = data.get("world_tick_index")
        snapshot_index = data.get("world_snapshot_index")
        if tick_index is None:
            tick_index = parse_index_from_world_id(data.get("world_tick_id"), prefix="WT")
        if snapshot_index is None:
            snapshot_index = parse_index_from_world_id(data.get("world_snapshot_id"), prefix="WM")
        return cls(
            world_tick_index=_non_negative_int(tick_index),
            world_snapshot_index=_non_negative_int(snapshot_index),
            sim_time_s=data.get("sim_time_s") or 0.0,
            source=data.get("source") or WorldSnapshotSource.READ,
            source_path=str(data.get("source_path") or "q_sim_service.WorldModel"),
            reason=str(data.get("reason") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


def normalize_world_snapshot_source(value: WorldSnapshotSource | str | None) -> WorldSnapshotSource:
    if isinstance(value, WorldSnapshotSource):
        return value
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "init": WorldSnapshotSource.INIT,
        "boot": WorldSnapshotSource.INIT,
        "tick": WorldSnapshotSource.TICK,
        "step": WorldSnapshotSource.TICK,
        "mutation": WorldSnapshotSource.MUTATION,
        "command": WorldSnapshotSource.MUTATION,
        "read": WorldSnapshotSource.READ,
        "state": WorldSnapshotSource.READ,
        "telemetry": WorldSnapshotSource.TELEMETRY,
        "sensor_runtime": WorldSnapshotSource.SENSOR_RUNTIME,
        "sensor": WorldSnapshotSource.SENSOR_RUNTIME,
        "sensor_observation": WorldSnapshotSource.SENSOR_OBSERVATION,
        "sensor_observations": WorldSnapshotSource.SENSOR_OBSERVATION,
        "observation": WorldSnapshotSource.SENSOR_OBSERVATION,
        "sensor_trust": WorldSnapshotSource.SENSOR_TRUST,
        "sensor_confidence": WorldSnapshotSource.SENSOR_TRUST,
        "trust": WorldSnapshotSource.SENSOR_TRUST,
        "radar": WorldSnapshotSource.RADAR,
        "objective_world": WorldSnapshotSource.OBJECTIVE_WORLD,
        "objective": WorldSnapshotSource.OBJECTIVE_WORLD,
        "scene": WorldSnapshotSource.OBJECTIVE_WORLD,
        "event": WorldSnapshotSource.EVENT,
        "events": WorldSnapshotSource.EVENT,
    }
    return aliases.get(text, WorldSnapshotSource.READ)


def parse_index_from_world_id(value: Any, *, prefix: str) -> int:
    token = str(value or "").strip().upper()
    expected = f"{prefix.upper()}-"
    if not token.startswith(expected):
        return 0
    try:
        return _non_negative_int(token[len(expected) :])
    except Exception:
        return 0


def world_snapshot_ref_from_state(state: Mapping[str, Any] | None, *, source: WorldSnapshotSource | str = WorldSnapshotSource.READ) -> WorldSnapshotRef:
    """Extract a snapshot ref from a WorldModel-style state mapping."""

    if not isinstance(state, Mapping):
        return WorldSnapshotRef(source=source)
    block = state.get("world_snapshot")
    if isinstance(block, Mapping):
        ref = WorldSnapshotRef.from_mapping(block)
        return WorldSnapshotRef(
            world_tick_index=ref.world_tick_index,
            world_snapshot_index=ref.world_snapshot_index,
            sim_time_s=ref.sim_time_s,
            source=source,
            source_path=ref.source_path,
            reason=ref.reason,
            metadata=ref.metadata,
        )
    return WorldSnapshotRef(
        world_tick_index=parse_index_from_world_id(state.get("world_tick_id"), prefix="WT"),
        world_snapshot_index=parse_index_from_world_id(state.get("world_snapshot_id"), prefix="WM"),
        sim_time_s=state.get("sim_time_s") or 0.0,
        source=source,
        source_path="q_sim_service.WorldModel.get_state",
    )


def _non_negative_int(value: int | str | None) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        parsed = int(value)
    except Exception:
        return 0
    return max(0, parsed)


def _finite_float(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    try:
        parsed = float(value)
    except Exception:
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0
