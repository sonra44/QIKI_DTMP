"""Multi-sensor observation ingestion contracts and normalization."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .event_store import EventStore, TruthState
from .radar_backends import RadarPoint, RadarScene


@dataclass(frozen=True)
class Observation:
    source_id: str
    t: float
    track_key: str
    pos_xy: tuple[float, float]
    vel_xy: tuple[float, float] | None
    quality: float
    err_radius: float | None = None
    covariance: tuple[float, float, float, float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceTrack:
    source_id: str
    source_track_id: str
    last_update_t: float
    state_pos_xy: tuple[float, float]
    state_vel_xy: tuple[float, float] | None
    quality: float
    trust: float
    err_radius: float | None = None
    covariance: tuple[float, float, float, float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _is_finite(value: float) -> bool:
    return math.isfinite(float(value))


def clamp_quality(raw: float) -> float:
    try:
        value = float(raw)
    except Exception:
        return 0.0
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def validate_observation(observation: Observation) -> tuple[bool, str]:
    if not str(observation.source_id).strip():
        return False, "MISSING_SOURCE_ID"
    if not str(observation.track_key).strip():
        return False, "MISSING_TRACK_KEY"
    if not _is_finite(observation.t):
        return False, "INVALID_TIMESTAMP"
    if len(observation.pos_xy) != 2:
        return False, "MISSING_POSITION"
    px, py = observation.pos_xy
    if not _is_finite(px) or not _is_finite(py):
        return False, "INVALID_POSITION"
    if observation.vel_xy is not None:
        if len(observation.vel_xy) != 2:
            return False, "INVALID_VELOCITY"
        vx, vy = observation.vel_xy
        if not _is_finite(vx) or not _is_finite(vy):
            return False, "INVALID_VELOCITY"
    return True, "OK"


def observation_to_source_track(observation: Observation) -> SourceTrack:
    quality = clamp_quality(observation.quality)
    return SourceTrack(
        source_id=observation.source_id,
        source_track_id=observation.track_key,
        last_update_t=float(observation.t),
        state_pos_xy=(float(observation.pos_xy[0]), float(observation.pos_xy[1])),
        state_vel_xy=(
            None
            if observation.vel_xy is None
            else (float(observation.vel_xy[0]), float(observation.vel_xy[1]))
        ),
        quality=quality,
        trust=quality,
        err_radius=observation.err_radius,
        covariance=observation.covariance,
        metadata=dict(observation.metadata),
    )


def ingest_observations(
    observations: list[Observation],
    *,
    event_store: EventStore | None = None,
    emit_observation_rx: bool = True,
) -> dict[str, list[SourceTrack]]:
    tracks_by_source: dict[str, dict[str, SourceTrack]] = {}
    for observation in observations:
        valid, reason = validate_observation(observation)
        if not valid:
            if event_store is not None:
                event_store.append_new(
                    subsystem="SENSORS",
                    event_type="SENSOR_OBSERVATION_DROPPED",
                    payload={
                        "source_id": str(observation.source_id),
                        "source_track_id": str(observation.track_key),
                        "t": observation.t,
                        "reason": reason,
                    },
                    truth_state=TruthState.INVALID,
                    reason=reason,
                )
            continue

        track = observation_to_source_track(observation)
        source_bucket = tracks_by_source.setdefault(track.source_id, {})
        source_bucket[track.source_track_id] = track

        if event_store is not None and emit_observation_rx:
            event_store.append_new(
                subsystem="SENSORS",
                event_type="SENSOR_OBSERVATION_RX",
                payload={
                    "source_id": track.source_id,
                    "source_track_id": track.source_track_id,
                    "t": track.last_update_t,
                    "pos": [track.state_pos_xy[0], track.state_pos_xy[1]],
                    "vel": (
                        None
                        if track.state_vel_xy is None
                        else [track.state_vel_xy[0], track.state_vel_xy[1]]
                    ),
                    "quality": track.quality,
                    "trust": track.trust,
                },
                truth_state=TruthState.OK,
                reason="OBSERVATION_RX",
            )
        if event_store is not None:
            event_store.append_new(
                subsystem="SENSORS",
                event_type="SOURCE_TRACK_UPDATED",
                payload={
                    "source_id": track.source_id,
                    "source_track_id": track.source_track_id,
                    "t": track.last_update_t,
                    "pos": [track.state_pos_xy[0], track.state_pos_xy[1]],
                    "vel": (
                        None
                        if track.state_vel_xy is None
                        else [track.state_vel_xy[0], track.state_vel_xy[1]]
                    ),
                    "quality": track.quality,
                    "trust": track.trust,
                },
                truth_state=TruthState.OK,
                reason="TRACK_UPDATED",
            )

    return {source_id: list(bucket.values()) for source_id, bucket in tracks_by_source.items()}


def source_tracks_to_scene(
    tracks_by_source: dict[str, list[SourceTrack]],
    *,
    truth_state: str = "OK",
    reason: str = "OK",
    is_fallback: bool = False,
) -> RadarScene:
    points: list[RadarPoint] = []
    source_count = len(tracks_by_source)
    for source_id, tracks in tracks_by_source.items():
        for index, track in enumerate(tracks):
            vx = track.state_vel_xy[0] if track.state_vel_xy is not None else 0.0
            vy = track.state_vel_xy[1] if track.state_vel_xy is not None else 0.0
            target_id = track.source_track_id if source_count == 1 else f"{source_id}:{track.source_track_id}"
            points.append(
                RadarPoint(
                    x=track.state_pos_xy[0],
                    y=track.state_pos_xy[1],
                    z=0.0,
                    vr_mps=float(math.hypot(vx, vy)),
                    metadata={
                        "target_id": target_id,
                        "source_id": source_id,
                        "source_track_id": track.source_track_id,
                        "quality": track.quality,
                        "trust": track.trust,
                        "track_index": index,
                    },
                )
            )
    return RadarScene(
        ok=bool(points),
        reason=reason if points else "NO_DATA",
        truth_state=truth_state if points else "NO_DATA",
        is_fallback=is_fallback,
        points=points,
    )

