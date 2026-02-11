"""Situation awareness engine for radar scenes (threats/CPA/alerts)."""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .radar_backends.base import RadarPoint, RadarScene
from .radar_render_policy import RadarRenderStats
from .radar_trail_store import RadarTrailStore
from .radar_view_state import RadarViewState


class SituationType(str, Enum):
    CPA_RISK = "CPA_RISK"
    CLOSING_FAST = "CLOSING_FAST"
    ZONE_VIOLATION = "ZONE_VIOLATION"
    LOST_CONTACT = "LOST_CONTACT"
    UNKNOWN_NEARBY = "UNKNOWN_NEARBY"


class SituationSeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Situation:
    id: str
    type: SituationType
    severity: SituationSeverity
    track_ids: tuple[str, ...]
    metrics: dict[str, float | str]
    created_ts: float
    last_update_ts: float
    is_active: bool


@dataclass(frozen=True)
class SituationDelta:
    event_type: str
    situation: Situation


@dataclass(frozen=True)
class SituationConfig:
    enabled: bool
    cpa_warn_t: float
    cpa_crit_t: float
    cpa_crit_dist: float
    closing_speed_warn: float
    near_dist: float
    near_recent_s: float
    closing_confirm_frames: int
    lost_contact_recent_s: float

    @classmethod
    def from_env(cls) -> "SituationConfig":
        return cls(
            enabled=_env_bool("RADAR_SITUATION_ENABLE", True),
            cpa_warn_t=_env_float("RADAR_CPA_WARN_T", 20.0),
            cpa_crit_t=_env_float("RADAR_CPA_CRIT_T", 8.0),
            cpa_crit_dist=_env_float("RADAR_CPA_CRIT_DIST", 150.0),
            closing_speed_warn=_env_float("RADAR_CLOSING_SPEED_WARN", 5.0),
            near_dist=_env_float("RADAR_NEAR_DIST", 300.0),
            near_recent_s=_env_float("RADAR_NEAR_RECENT_S", 8.0),
            closing_confirm_frames=max(2, _env_int("RADAR_CLOSING_CONFIRM_FRAMES", 3)),
            lost_contact_recent_s=_env_float("RADAR_LOST_CONTACT_RECENT_S", 10.0),
        )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "1" if default else "0").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _distance(point: RadarPoint) -> float:
    return math.sqrt((point.x * point.x) + (point.y * point.y) + (point.z * point.z))


def _closing_speed(point: RadarPoint) -> float:
    # By contract, negative vr_mps means approaching target.
    return max(0.0, -float(point.vr_mps))


def _is_unknown(point: RadarPoint) -> bool:
    iff = str(point.metadata.get("iff", "")).strip().upper()
    obj = str(point.metadata.get("object_type", "")).strip().upper()
    if iff in {"UNKNOWN", "UNIDENTIFIED", "U"}:
        return True
    if obj in {"UNKNOWN", "UNIDENTIFIED", "UNSPECIFIED", ""}:
        return True
    return False


def _point_age_s(point: RadarPoint) -> float | None:
    value = point.metadata.get("age_s")
    try:
        age = float(value)
    except Exception:
        return None
    if not math.isfinite(age):
        return None
    return max(0.0, age)


def _track_id(point: RadarPoint, idx: int) -> str:
    return str(point.metadata.get("target_id") or point.metadata.get("id") or f"target-{idx}")


class RadarSituationEngine:
    def __init__(self, config: SituationConfig | None = None):
        self.config = config or SituationConfig.from_env()
        self._active: dict[str, Situation] = {}
        self._last_seen_ts: dict[str, float] = {}
        self._prev_track_ids: set[str] = set()

    def evaluate(
        self,
        scene: RadarScene,
        *,
        trail_store: RadarTrailStore,
        view_state: RadarViewState,
        render_stats: RadarRenderStats | None,
    ) -> tuple[list[Situation], list[SituationDelta]]:
        del view_state  # reserved for v2 contextual rules
        del render_stats
        if not self.config.enabled:
            return [], []

        now_ts = time.time()
        candidates: dict[str, Situation] = {}

        if scene.ok:
            points_by_track: dict[str, RadarPoint] = {}
            for idx, point in enumerate(scene.points):
                points_by_track[_track_id(point, idx)] = point

            for track_id, point in points_by_track.items():
                self._last_seen_ts[track_id] = now_ts
                dist = _distance(point)
                closing = _closing_speed(point)
                t_cpa = dist / closing if closing > 1e-9 else float("inf")

                if closing > 0 and t_cpa < self.config.cpa_warn_t:
                    severity = SituationSeverity.WARN
                    if t_cpa < self.config.cpa_crit_t and dist < self.config.cpa_crit_dist:
                        severity = SituationSeverity.CRITICAL
                    candidates[f"cpa:{track_id}"] = Situation(
                        id=f"cpa:{track_id}",
                        type=SituationType.CPA_RISK,
                        severity=severity,
                        track_ids=(track_id,),
                        metrics={
                            "distance_m": round(dist, 3),
                            "time_to_cpa_s": round(t_cpa, 3) if math.isfinite(t_cpa) else "inf",
                            "closing_speed_mps": round(closing, 3),
                        },
                        created_ts=now_ts,
                        last_update_ts=now_ts,
                        is_active=True,
                    )

                if closing > self.config.closing_speed_warn and self._is_distance_decreasing(trail_store, track_id):
                    candidates[f"closing:{track_id}"] = Situation(
                        id=f"closing:{track_id}",
                        type=SituationType.CLOSING_FAST,
                        severity=SituationSeverity.WARN,
                        track_ids=(track_id,),
                        metrics={
                            "distance_m": round(dist, 3),
                            "closing_speed_mps": round(closing, 3),
                        },
                        created_ts=now_ts,
                        last_update_ts=now_ts,
                        is_active=True,
                    )

                age_s = _point_age_s(point)
                if _is_unknown(point) and dist < self.config.near_dist and (age_s is None or age_s <= self.config.near_recent_s):
                    candidates[f"unknown:{track_id}"] = Situation(
                        id=f"unknown:{track_id}",
                        type=SituationType.UNKNOWN_NEARBY,
                        severity=SituationSeverity.WARN,
                        track_ids=(track_id,),
                        metrics={
                            "distance_m": round(dist, 3),
                            "age_s": round(age_s, 3) if age_s is not None else "n/a",
                        },
                        created_ts=now_ts,
                        last_update_ts=now_ts,
                        is_active=True,
                    )

            lost_tracks = sorted(self._prev_track_ids - set(points_by_track.keys()))
            for track_id in lost_tracks:
                seen_ts = self._last_seen_ts.get(track_id, 0.0)
                if now_ts - seen_ts > self.config.lost_contact_recent_s:
                    continue
                candidates[f"lost:{track_id}"] = Situation(
                    id=f"lost:{track_id}",
                    type=SituationType.LOST_CONTACT,
                    severity=SituationSeverity.WARN,
                    track_ids=(track_id,),
                    metrics={"last_seen_age_s": round(now_ts - seen_ts, 3)},
                    created_ts=now_ts,
                    last_update_ts=now_ts,
                    is_active=True,
                )
            self._prev_track_ids = set(points_by_track.keys())
        else:
            # Truth rule: no-data frame does not create new situations.
            candidates = {}

        deltas: list[SituationDelta] = []
        next_active: dict[str, Situation] = {}

        for situation_id, candidate in candidates.items():
            previous = self._active.get(situation_id)
            if previous is None:
                created = Situation(
                    id=candidate.id,
                    type=candidate.type,
                    severity=candidate.severity,
                    track_ids=candidate.track_ids,
                    metrics=dict(candidate.metrics),
                    created_ts=candidate.created_ts,
                    last_update_ts=candidate.last_update_ts,
                    is_active=True,
                )
                deltas.append(SituationDelta(event_type="SITUATION_CREATED", situation=created))
                next_active[situation_id] = created
                continue
            updated = Situation(
                id=previous.id,
                type=candidate.type,
                severity=candidate.severity,
                track_ids=candidate.track_ids,
                metrics=dict(candidate.metrics),
                created_ts=previous.created_ts,
                last_update_ts=now_ts,
                is_active=True,
            )
            next_active[situation_id] = updated
            if self._changed(previous, updated):
                deltas.append(SituationDelta(event_type="SITUATION_UPDATED", situation=updated))

        for situation_id, previous in self._active.items():
            if situation_id in next_active:
                continue
            resolved = Situation(
                id=previous.id,
                type=previous.type,
                severity=previous.severity,
                track_ids=previous.track_ids,
                metrics=dict(previous.metrics),
                created_ts=previous.created_ts,
                last_update_ts=now_ts,
                is_active=False,
            )
            deltas.append(SituationDelta(event_type="SITUATION_RESOLVED", situation=resolved))

        self._active = next_active
        situations = sorted(self._active.values(), key=lambda s: (_severity_rank(s.severity), s.id))
        return situations, deltas

    def _is_distance_decreasing(self, trail_store: RadarTrailStore, track_id: str) -> bool:
        trail = trail_store.get_trail(track_id)
        required = self.config.closing_confirm_frames
        if len(trail) < required:
            return False
        distances = [_distance(point) for point in trail[-required:]]
        for prev, cur in zip(distances, distances[1:]):
            if not (cur < prev):
                return False
        return True

    @staticmethod
    def _changed(old: Situation, new: Situation) -> bool:
        return old.severity != new.severity or old.metrics != new.metrics or old.track_ids != new.track_ids


def _severity_rank(severity: SituationSeverity) -> int:
    if severity == SituationSeverity.CRITICAL:
        return 0
    if severity == SituationSeverity.WARN:
        return 1
    return 2


def summarize_situations(situations: Iterable[Situation]) -> dict[str, int]:
    counts = {"CRITICAL": 0, "WARN": 0, "INFO": 0}
    for situation in situations:
        counts[situation.severity.value] = counts.get(situation.severity.value, 0) + 1
    return counts
