"""Multi-sensor fusion v1: deterministic association + majority vote."""

from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass, field
from typing import Iterable

from .radar_backends import RadarPoint, RadarScene
from .radar_ingestion import SourceTrack


def _truthy(raw: str) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _safe_float(raw: str, default: float) -> float:
    try:
        value = float(raw)
    except Exception:
        return default
    if not math.isfinite(value):
        return default
    return value


def _safe_int(raw: str, default: int) -> int:
    try:
        value = int(raw)
    except Exception:
        return default
    return value


@dataclass(frozen=True)
class FusionConfig:
    enabled: bool
    gate_dist_m: float
    gate_vel_mps: float
    min_support: int
    max_age_s: float
    conflict_dist_m: float
    confirm_frames: int
    cooldown_s: float

    @classmethod
    def from_env(cls) -> "FusionConfig":
        gate_dist = max(0.0, _safe_float(os.getenv("RADAR_FUSION_GATE_DIST_M", "50.0"), 50.0))
        conflict_default = gate_dist * 2.0
        return cls(
            enabled=_truthy(os.getenv("RADAR_FUSION_ENABLED", "0")),
            gate_dist_m=gate_dist,
            gate_vel_mps=max(0.0, _safe_float(os.getenv("RADAR_FUSION_GATE_VEL_MPS", "20.0"), 20.0)),
            min_support=max(1, _safe_int(os.getenv("RADAR_FUSION_MIN_SUPPORT", "2"), 2)),
            max_age_s=max(0.0, _safe_float(os.getenv("RADAR_FUSION_MAX_AGE_S", "2.0"), 2.0)),
            conflict_dist_m=max(
                0.0,
                _safe_float(
                    os.getenv("RADAR_FUSION_CONFLICT_DIST_M", f"{conflict_default}"),
                    conflict_default,
                ),
            ),
            confirm_frames=max(1, _safe_int(os.getenv("RADAR_FUSION_CONFIRM_FRAMES", "3"), 3)),
            cooldown_s=max(0.0, _safe_float(os.getenv("RADAR_FUSION_COOLDOWN_S", "2.0"), 2.0)),
        )


@dataclass(frozen=True)
class Contributor:
    source_id: str
    source_track_id: str
    quality: float
    trust: float
    pos_xy: tuple[float, float]
    vel_xy: tuple[float, float] | None
    dt: float
    last_update_t: float

    @property
    def key(self) -> str:
        return f"{self.source_id}:{self.source_track_id}"


@dataclass(frozen=True)
class FusionCluster:
    contributors: tuple[Contributor, ...]
    support_ok: bool
    spread_pos: float


@dataclass(frozen=True)
class FusedTrack:
    fused_id: str
    last_update_t: float
    pos_xy: tuple[float, float]
    vel_xy: tuple[float, float] | None
    trust: float
    contributors: tuple[Contributor, ...]
    flags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class FusedTrackSet:
    tracks: tuple[FusedTrack, ...]
    clusters: tuple[FusionCluster, ...]
    diagnostics: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _PendingCandidate:
    track: FusedTrack
    hits: int
    first_seen_t: float


@dataclass(frozen=True)
class FusionStateStore:
    active_tracks: dict[str, FusedTrack] = field(default_factory=dict)
    pending_tracks: dict[str, _PendingCandidate] = field(default_factory=dict)
    cooldown_until: dict[str, float] = field(default_factory=dict)


def _dist2(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = float(a[0]) - float(b[0])
    dy = float(a[1]) - float(b[1])
    return (dx * dx) + (dy * dy)


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.sqrt(_dist2(a, b))


def _cluster_signature(contributors: Iterable[Contributor]) -> tuple[str, ...]:
    return tuple(sorted(c.key for c in contributors))


def _stable_support_id(contributors: Iterable[Contributor]) -> str:
    digest = hashlib.sha1(",".join(sorted(c.key for c in contributors)).encode("utf-8")).hexdigest()
    return f"fused:{digest[:12]}"


def _to_contributors(
    tracks_by_source: dict[str, list[SourceTrack]],
) -> tuple[list[Contributor], list[Contributor]]:
    reference_t = 0.0
    for tracks in tracks_by_source.values():
        for track in tracks:
            reference_t = max(reference_t, float(track.last_update_t))
    fresh: list[Contributor] = []
    stale: list[Contributor] = []
    for source_id in sorted(tracks_by_source.keys()):
        tracks = sorted(
            tracks_by_source[source_id],
            key=lambda track: (-(float(track.trust)), str(track.source_track_id)),
        )
        for track in tracks:
            dt = max(0.0, reference_t - float(track.last_update_t))
            contributor = Contributor(
                source_id=track.source_id,
                source_track_id=track.source_track_id,
                quality=float(track.quality),
                trust=float(track.trust),
                pos_xy=(float(track.state_pos_xy[0]), float(track.state_pos_xy[1])),
                vel_xy=(
                    None
                    if track.state_vel_xy is None
                    else (float(track.state_vel_xy[0]), float(track.state_vel_xy[1]))
                ),
                dt=dt,
                last_update_t=float(track.last_update_t),
            )
            stale.append(contributor)
            fresh.append(contributor)
    return fresh, stale


def _passes_gate(seed: Contributor, candidate: Contributor, cfg: FusionConfig) -> bool:
    if _dist(seed.pos_xy, candidate.pos_xy) > cfg.gate_dist_m:
        return False
    if seed.vel_xy is not None and candidate.vel_xy is not None:
        if _dist(seed.vel_xy, candidate.vel_xy) > cfg.gate_vel_mps:
            return False
    return True


def _spread(contributors: tuple[Contributor, ...]) -> float:
    if len(contributors) <= 1:
        return 0.0
    max_dist = 0.0
    for i in range(len(contributors)):
        for j in range(i + 1, len(contributors)):
            max_dist = max(max_dist, _dist(contributors[i].pos_xy, contributors[j].pos_xy))
    return max_dist


def associate(
    tracks_by_source: dict[str, list[SourceTrack]],
    cfg: FusionConfig,
) -> tuple[list[FusionCluster], int]:
    all_candidates, _stale_shadow = _to_contributors(tracks_by_source)
    fresh = [candidate for candidate in all_candidates if candidate.dt <= cfg.max_age_s]
    stale_count = len(all_candidates) - len(fresh)
    ordered = sorted(
        fresh,
        key=lambda candidate: (-candidate.trust, candidate.source_id, candidate.source_track_id),
    )
    used_keys: set[str] = set()
    clusters: list[FusionCluster] = []
    for seed in ordered:
        if seed.key in used_keys:
            continue
        selected = [seed]
        used_keys.add(seed.key)
        seen_sources = {seed.source_id}
        for source_id in sorted({candidate.source_id for candidate in ordered}):
            if source_id in seen_sources:
                continue
            candidates = [
                candidate
                for candidate in ordered
                if candidate.source_id == source_id
                and candidate.key not in used_keys
                and _passes_gate(seed, candidate, cfg)
            ]
            if not candidates:
                continue
            nearest = min(
                candidates,
                key=lambda candidate: (_dist(seed.pos_xy, candidate.pos_xy), -candidate.trust, candidate.source_track_id),
            )
            selected.append(nearest)
            used_keys.add(nearest.key)
            seen_sources.add(nearest.source_id)
        contributors = tuple(
            sorted(selected, key=lambda c: (c.source_id, c.source_track_id))
        )
        clusters.append(
            FusionCluster(
                contributors=contributors,
                support_ok=len(contributors) >= cfg.min_support,
                spread_pos=_spread(contributors),
            )
        )
    clusters.sort(key=lambda cluster: _cluster_signature(cluster.contributors))
    return clusters, stale_count


def _weighted_average(values: list[tuple[tuple[float, float], float]]) -> tuple[float, float]:
    weight_sum = sum(weight for _value, weight in values)
    if weight_sum <= 0.0:
        simple_x = sum(value[0] for value, _weight in values) / float(len(values))
        simple_y = sum(value[1] for value, _weight in values) / float(len(values))
        return (simple_x, simple_y)
    x = sum(value[0] * weight for value, weight in values) / weight_sum
    y = sum(value[1] * weight for value, weight in values) / weight_sum
    return (x, y)


def fuse(clusters: list[FusionCluster], cfg: FusionConfig) -> list[FusedTrack]:
    fused_tracks: list[FusedTrack] = []
    for cluster in clusters:
        contributors = cluster.contributors
        weights = [(contributor.pos_xy, max(0.0, contributor.trust)) for contributor in contributors]
        pos_xy = _weighted_average(weights)
        vel_values = [
            (contributor.vel_xy, max(0.0, contributor.trust))
            for contributor in contributors
            if contributor.vel_xy is not None
        ]
        vel_xy = _weighted_average(vel_values) if len(vel_values) >= 2 else None
        avg_trust = sum(max(0.0, contributor.trust) for contributor in contributors) / float(len(contributors))
        flags: set[str] = set()
        trust = avg_trust
        support_ok = len(contributors) >= cfg.min_support
        if support_ok:
            trust = min(1.0, trust + 0.1)
            fused_id = _stable_support_id(contributors)
        else:
            flags.add("LOW_SUPPORT")
            trust = min(trust, 0.49)
            lead = min(contributors, key=lambda c: (c.source_id, c.source_track_id))
            fused_id = f"{lead.source_id}:{lead.source_track_id}"
        if cluster.spread_pos > cfg.conflict_dist_m:
            flags.add("CONFLICT")
            trust *= 0.5
        trust = max(0.0, min(1.0, trust))
        fused_tracks.append(
            FusedTrack(
                fused_id=fused_id,
                last_update_t=max(contributor.last_update_t for contributor in contributors),
                pos_xy=(float(pos_xy[0]), float(pos_xy[1])),
                vel_xy=(None if vel_xy is None else (float(vel_xy[0]), float(vel_xy[1]))),
                trust=trust,
                contributors=contributors,
                flags=frozenset(sorted(flags)),
            )
        )
    fused_tracks.sort(key=lambda track: track.fused_id)
    return fused_tracks


def _track_similarity(candidate: FusedTrack, previous: FusedTrack, cfg: FusionConfig) -> float:
    candidate_keys = {contributor.key for contributor in candidate.contributors}
    previous_keys = {contributor.key for contributor in previous.contributors}
    overlap = len(candidate_keys & previous_keys) / float(max(1, len(previous_keys)))
    if overlap >= 0.5:
        return overlap + 1.0
    if _dist(candidate.pos_xy, previous.pos_xy) <= cfg.gate_dist_m:
        return 0.75
    return 0.0


def _state_key(track: FusedTrack) -> str:
    return ",".join(sorted(contributor.key for contributor in track.contributors))


def update_fusion_state(
    prev_state: FusionStateStore,
    fused_tracks: list[FusedTrack],
    cfg: FusionConfig,
    now: float,
) -> FusionStateStore:
    active_prev = dict(prev_state.active_tracks)
    pending_prev = dict(prev_state.pending_tracks)
    cooldown_prev = dict(prev_state.cooldown_until)
    next_active: dict[str, FusedTrack] = {}
    next_pending: dict[str, _PendingCandidate] = {}
    matched_prev_ids: set[str] = set()
    for candidate in fused_tracks:
        best_match_id: str | None = None
        best_score = 0.0
        for prev_id, previous in active_prev.items():
            score = _track_similarity(candidate, previous, cfg)
            if score > best_score:
                best_score = score
                best_match_id = prev_id
        if best_match_id is not None and best_score > 0.0:
            matched_prev_ids.add(best_match_id)
            next_active[best_match_id] = FusedTrack(
                fused_id=best_match_id,
                last_update_t=candidate.last_update_t,
                pos_xy=candidate.pos_xy,
                vel_xy=candidate.vel_xy,
                trust=candidate.trust,
                contributors=candidate.contributors,
                flags=candidate.flags,
            )
            continue
        key = _state_key(candidate)
        cooldown_until = cooldown_prev.get(key, 0.0)
        if now < cooldown_until:
            continue
        pending = pending_prev.get(key)
        hits = 1 if pending is None else (pending.hits + 1)
        first_seen_t = now if pending is None else pending.first_seen_t
        if hits >= cfg.confirm_frames:
            next_active[candidate.fused_id] = candidate
        else:
            next_pending[key] = _PendingCandidate(track=candidate, hits=hits, first_seen_t=first_seen_t)
    for prev_id, previous in active_prev.items():
        if prev_id in matched_prev_ids:
            continue
        if now - float(previous.last_update_t) <= cfg.max_age_s:
            next_active[prev_id] = previous
            continue
        cooldown_prev[_state_key(previous)] = now + cfg.cooldown_s
    next_cooldown = {
        key: until_ts for key, until_ts in cooldown_prev.items() if until_ts > now
    }
    return FusionStateStore(
        active_tracks=next_active,
        pending_tracks=next_pending,
        cooldown_until=next_cooldown,
    )


def fuse_tracks(
    tracks_by_source: dict[str, list[SourceTrack]],
    *,
    cfg: FusionConfig,
    prev_state: FusionStateStore | None,
    now: float,
) -> tuple[FusedTrackSet, FusionStateStore]:
    clusters, stale_count = associate(tracks_by_source, cfg)
    fused_raw = fuse(clusters, cfg)
    state = update_fusion_state(prev_state or FusionStateStore(), fused_raw, cfg, now)
    active_tracks = sorted(state.active_tracks.values(), key=lambda track: track.fused_id)
    diagnostics = {
        "cluster_count": len(clusters),
        "stale_contributors": stale_count,
        "active_tracks": len(active_tracks),
        "pending_tracks": len(state.pending_tracks),
    }
    return (
        FusedTrackSet(
            tracks=tuple(active_tracks),
            clusters=tuple(clusters),
            diagnostics=diagnostics,
        ),
        state,
    )


def fused_tracks_to_scene(
    track_set: FusedTrackSet,
    *,
    truth_state: str = "OK",
    reason: str = "OK",
    is_fallback: bool = False,
) -> RadarScene:
    points: list[RadarPoint] = []
    for index, track in enumerate(track_set.tracks):
        vx = track.vel_xy[0] if track.vel_xy is not None else 0.0
        vy = track.vel_xy[1] if track.vel_xy is not None else 0.0
        points.append(
            RadarPoint(
                x=float(track.pos_xy[0]),
                y=float(track.pos_xy[1]),
                z=0.0,
                vr_mps=float(math.hypot(vx, vy)),
                metadata={
                    "target_id": track.fused_id,
                    "fused_id": track.fused_id,
                    "fused_trust": float(track.trust),
                    "fused_flags": sorted(track.flags),
                    "contributors": [
                        {
                            "source_id": contributor.source_id,
                            "source_track_id": contributor.source_track_id,
                            "trust": float(contributor.trust),
                            "quality": float(contributor.quality),
                            "dt": float(contributor.dt),
                        }
                        for contributor in track.contributors
                    ],
                    "track_index": index,
                },
            )
        )
    effective_reason = reason
    if points and track_set.diagnostics.get("stale_contributors", 0):
        effective_reason = "OK_WITH_STALE"
    return RadarScene(
        ok=bool(points),
        reason=effective_reason if points else "NO_DATA",
        truth_state=truth_state if points else "NO_DATA",
        is_fallback=is_fallback,
        points=points,
    )
