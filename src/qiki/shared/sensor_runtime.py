from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Mapping, Sequence


class SensorStatus(StrEnum):
    OK = "OK"
    WARN = "WARN"
    DEGRADED = "DEGRADED"
    FAULT = "FAULT"
    OFFLINE = "OFFLINE"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


class SensorSourceKind(StrEnum):
    LIVE = "LIVE"
    DERIVED = "DERIVED"
    CONFIG = "CONFIG"
    MISSING = "MISSING"


class SensorFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    DEAD = "dead"
    ABSENT = "absent"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SensorReadingSnapshot:
    """Canonical runtime sensor reading used inside QIKI Python code.

    This object is deliberately protobuf-free.  It is an internal truth contract:
    a reading must state where it came from, when it was observed, whether it is
    live or derived/config-only, and how much confidence the producing layer can
    honestly attach to it.
    """

    sensor_id: str
    sensor_type: str
    subsystem: str
    status: SensorStatus | str
    timestamp_epoch_s: float | None
    source_kind: SensorSourceKind | str
    source_path: str
    value: Any = None
    unit: str = ""
    confidence: float | None = None
    quality: float | None = None
    freshness_ms: float | None = None
    evidence: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    world_snapshot_id: str | None = None
    source_world_snapshot_id: str | None = None
    observation_id: str | None = None
    observation_kind: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sensor_id", str(self.sensor_id or "unknown"))
        object.__setattr__(self, "sensor_type", str(self.sensor_type or "unknown"))
        object.__setattr__(self, "subsystem", str(self.subsystem or "sensors"))
        object.__setattr__(self, "status", normalize_sensor_status(self.status))
        object.__setattr__(self, "source_kind", normalize_source_kind(self.source_kind))
        object.__setattr__(self, "source_path", str(self.source_path or "unknown"))
        object.__setattr__(self, "confidence", _clamp01_or_none(self.confidence))
        object.__setattr__(self, "quality", _clamp01_or_none(self.quality))
        object.__setattr__(self, "timestamp_epoch_s", _finite_float_or_none(self.timestamp_epoch_s))
        object.__setattr__(self, "freshness_ms", _finite_float_or_none(self.freshness_ms))
        object.__setattr__(self, "evidence", tuple(str(item) for item in (self.evidence or ()) if str(item).strip()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))
        object.__setattr__(self, "world_snapshot_id", _str_or_none(self.world_snapshot_id))
        object.__setattr__(self, "source_world_snapshot_id", _str_or_none(self.source_world_snapshot_id) or _str_or_none(self.world_snapshot_id))
        object.__setattr__(self, "observation_id", _str_or_none(self.observation_id))
        object.__setattr__(self, "observation_kind", _str_or_none(self.observation_kind))

    @property
    def live(self) -> bool:
        return self.source_kind is SensorSourceKind.LIVE and self.timestamp_epoch_s is not None

    @property
    def usable(self) -> bool:
        return self.live and self.status in {SensorStatus.OK, SensorStatus.WARN, SensorStatus.DEGRADED}

    def freshness(self, *, now_ts: float | None = None, stale_after_s: float = 5.0, dead_after_s: float = 30.0) -> SensorFreshness:
        if self.source_kind is SensorSourceKind.MISSING:
            return SensorFreshness.ABSENT
        if self.timestamp_epoch_s is None:
            return SensorFreshness.UNKNOWN if self.source_kind is SensorSourceKind.LIVE else SensorFreshness.ABSENT
        now = time.time() if now_ts is None else float(now_ts)
        age = max(0.0, now - float(self.timestamp_epoch_s))
        if age >= dead_after_s:
            return SensorFreshness.DEAD
        if age >= stale_after_s:
            return SensorFreshness.STALE
        return SensorFreshness.FRESH

    def with_freshness(self, *, now_ts: float | None = None) -> SensorReadingSnapshot:
        if self.timestamp_epoch_s is None:
            return self
        now = time.time() if now_ts is None else float(now_ts)
        return replace(self, freshness_ms=max(0.0, (now - float(self.timestamp_epoch_s)) * 1000.0))

    def to_mapping(self, *, now_ts: float | None = None) -> dict[str, Any]:
        fresh = self.freshness(now_ts=now_ts)
        age_s = None
        if self.timestamp_epoch_s is not None:
            age_s = max(0.0, (time.time() if now_ts is None else float(now_ts)) - float(self.timestamp_epoch_s))
        out = {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "subsystem": self.subsystem,
            "status": self.status.value,
            "value": self.value,
            "unit": self.unit,
            "confidence": self.confidence,
            "quality": self.quality,
            "timestamp_epoch_s": self.timestamp_epoch_s,
            "source_kind": self.source_kind.value,
            "source_path": self.source_path,
            "freshness": fresh.value,
            "freshness_ms": self.freshness_ms,
            "age_s": age_s,
            "is_live": self.live,
            "is_usable": self.usable,
            "evidence": list(self.evidence),
            "metadata": dict(self.metadata or {}),
        }
        if self.world_snapshot_id is not None:
            out["world_snapshot_id"] = self.world_snapshot_id
        if self.source_world_snapshot_id is not None:
            out["source_world_snapshot_id"] = self.source_world_snapshot_id
        if self.observation_id is not None:
            out["observation_id"] = self.observation_id
        if self.observation_kind is not None:
            out["observation_kind"] = self.observation_kind
        return out

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> SensorReadingSnapshot:
        return cls(
            sensor_id=str(data.get("sensor_id") or data.get("id") or data.get("key") or "unknown"),
            sensor_type=str(data.get("sensor_type") or data.get("type") or "unknown"),
            subsystem=str(data.get("subsystem") or "sensors"),
            status=data.get("status") or SensorStatus.UNKNOWN,
            value=data.get("value"),
            unit=str(data.get("unit") or ""),
            confidence=data.get("confidence"),
            quality=data.get("quality"),
            timestamp_epoch_s=data.get("timestamp_epoch_s") or data.get("timestamp") or data.get("ts_epoch"),
            source_kind=data.get("source_kind") or data.get("source") or SensorSourceKind.MISSING,
            source_path=str(data.get("source_path") or "unknown"),
            freshness_ms=data.get("freshness_ms"),
            evidence=tuple(data.get("evidence") or ()),
            metadata=dict(data.get("metadata") or {}),
            world_snapshot_id=data.get("world_snapshot_id"),
            source_world_snapshot_id=data.get("source_world_snapshot_id") or data.get("world_snapshot_id"),
            observation_id=data.get("observation_id"),
            observation_kind=data.get("observation_kind"),
        )


@dataclass(frozen=True, slots=True)
class SensorFrameSnapshot:
    readings: tuple[SensorReadingSnapshot, ...]
    generated_at_epoch_s: float
    source_path: str = "sensor_runtime.frame"
    world_tick_id: str | None = None
    world_snapshot_id: str | None = None
    source_world_snapshot_id: str | None = None
    sim_time_s: float | None = None
    sensor_observation: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "readings", tuple(self.readings or ()))
        object.__setattr__(self, "generated_at_epoch_s", float(self.generated_at_epoch_s))
        object.__setattr__(self, "source_path", str(self.source_path or "sensor_runtime.frame"))
        object.__setattr__(self, "world_tick_id", _str_or_none(self.world_tick_id))
        object.__setattr__(self, "world_snapshot_id", _str_or_none(self.world_snapshot_id))
        object.__setattr__(self, "source_world_snapshot_id", _str_or_none(self.source_world_snapshot_id))
        object.__setattr__(self, "sim_time_s", _finite_float_or_none(self.sim_time_s))
        object.__setattr__(self, "sensor_observation", dict(self.sensor_observation or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def by_id(self, sensor_id: str) -> SensorReadingSnapshot | None:
        wanted = str(sensor_id)
        for reading in self.readings:
            if reading.sensor_id == wanted:
                return reading
        return None

    def to_mapping(self) -> dict[str, Any]:
        out = {
            "generated_at_epoch_s": self.generated_at_epoch_s,
            "source_path": self.source_path,
            "readings": [item.to_mapping(now_ts=self.generated_at_epoch_s) for item in self.readings],
        }
        if self.world_tick_id is not None:
            out["world_tick_id"] = self.world_tick_id
        if self.world_snapshot_id is not None:
            out["world_snapshot_id"] = self.world_snapshot_id
        if self.source_world_snapshot_id is not None:
            out["source_world_snapshot_id"] = self.source_world_snapshot_id
        if self.sim_time_s is not None:
            out["sim_time_s"] = self.sim_time_s
        if self.sensor_observation:
            out["sensor_observation"] = dict(self.sensor_observation)
            observation_frame_id = self.sensor_observation.get("observation_frame_id")
            if observation_frame_id:
                out["observation_frame_id"] = observation_frame_id
        if self.metadata:
            out["metadata"] = dict(self.metadata)
        return out

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> SensorFrameSnapshot:
        raw_readings = data.get("readings") or data.get("sensors") or ()
        readings: list[SensorReadingSnapshot] = []
        if isinstance(raw_readings, Mapping):
            raw_iter = raw_readings.values()
        else:
            raw_iter = raw_readings if isinstance(raw_readings, Sequence) and not isinstance(raw_readings, (str, bytes)) else ()
        for item in raw_iter:
            if isinstance(item, SensorReadingSnapshot):
                readings.append(item)
            elif isinstance(item, Mapping):
                readings.append(SensorReadingSnapshot.from_mapping(item))
        generated = data.get("generated_at_epoch_s") or data.get("timestamp_epoch_s") or time.time()
        return cls(
            tuple(readings),
            float(generated),
            str(data.get("source_path") or "sensor_runtime.frame"),
            world_tick_id=data.get("world_tick_id"),
            world_snapshot_id=data.get("world_snapshot_id"),
            source_world_snapshot_id=data.get("source_world_snapshot_id") or data.get("world_snapshot_id"),
            sim_time_s=data.get("sim_time_s"),
            sensor_observation=dict(data.get("sensor_observation") or {}),
            metadata=dict(data.get("metadata") or {}),
        )


def normalize_sensor_status(value: SensorStatus | str | None) -> SensorStatus:
    if isinstance(value, SensorStatus):
        return value
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "ok": SensorStatus.OK,
        "healthy": SensorStatus.OK,
        "nominal": SensorStatus.OK,
        "locked": SensorStatus.OK,
        "online": SensorStatus.OK,
        "active": SensorStatus.OK,
        "warn": SensorStatus.WARN,
        "warning": SensorStatus.WARN,
        "degraded": SensorStatus.DEGRADED,
        "stale": SensorStatus.DEGRADED,
        "fault": SensorStatus.FAULT,
        "failed": SensorStatus.FAULT,
        "failure": SensorStatus.FAULT,
        "error": SensorStatus.FAULT,
        "offline": SensorStatus.OFFLINE,
        "off": SensorStatus.OFFLINE,
        "disabled": SensorStatus.OFFLINE,
        "configured_disabled": SensorStatus.OFFLINE,
        "missing": SensorStatus.MISSING,
        "absent": SensorStatus.MISSING,
        "нет_данных": SensorStatus.MISSING,
        "unknown": SensorStatus.UNKNOWN,
        "": SensorStatus.UNKNOWN,
    }
    return aliases.get(text, SensorStatus.UNKNOWN)


def normalize_source_kind(value: SensorSourceKind | str | None) -> SensorSourceKind:
    if isinstance(value, SensorSourceKind):
        return value
    text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "LIVE": SensorSourceKind.LIVE,
        "RAW_RUNTIME": SensorSourceKind.LIVE,
        "RUNTIME": SensorSourceKind.LIVE,
        "DERIVED": SensorSourceKind.DERIVED,
        "DERIVED_PROJECTION": SensorSourceKind.DERIVED,
        "PROJECTION": SensorSourceKind.DERIVED,
        "CONFIG": SensorSourceKind.CONFIG,
        "CONFIG_ONLY": SensorSourceKind.CONFIG,
        "INVENTORY_ONLY": SensorSourceKind.CONFIG,
        "MISSING": SensorSourceKind.MISSING,
        "ABSENT": SensorSourceKind.MISSING,
        "UNKNOWN": SensorSourceKind.MISSING,
        "": SensorSourceKind.MISSING,
    }
    return aliases.get(text, SensorSourceKind.MISSING)


def sensor_source_class(reading: SensorReadingSnapshot) -> str:
    if reading.source_kind is SensorSourceKind.LIVE:
        return "raw_runtime"
    if reading.source_kind is SensorSourceKind.DERIVED:
        return "derived_projection"
    if reading.source_kind is SensorSourceKind.CONFIG:
        return "inventory_only"
    return "inventory_only"


def sensor_trust_key(reading: SensorReadingSnapshot) -> str:
    if reading.status is SensorStatus.OK:
        return "healthy"
    if reading.status in {SensorStatus.WARN, SensorStatus.DEGRADED}:
        return "degraded"
    if reading.status in {SensorStatus.FAULT, SensorStatus.MISSING}:
        return "failed"
    if reading.status is SensorStatus.OFFLINE:
        return "off"
    return "unknown"


def sensor_status_ru(reading: SensorReadingSnapshot) -> str:
    return {
        SensorStatus.OK: "healthy",
        SensorStatus.WARN: "warn",
        SensorStatus.DEGRADED: "degraded",
        SensorStatus.FAULT: "failed",
        SensorStatus.OFFLINE: "off",
        SensorStatus.MISSING: "Нет данных",
        SensorStatus.UNKNOWN: "unknown",
    }[reading.status]


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clamp01_or_none(value: Any) -> float | None:
    parsed = _finite_float_or_none(value)
    if parsed is None:
        return None
    return max(0.0, min(1.0, parsed))


def _finite_float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None
