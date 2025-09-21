"""Stateful radar track store with simple alpha-beta filtering."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from qiki.shared.models.radar import (
    RadarDetectionModel,
    RadarFrameModel,
    RadarTrackModel,
    RadarTrackStatusEnum,
    FriendFoeEnum,
    ObjectTypeEnum,
    TransponderModeEnum,
    Vector3Model,
)


@dataclass
class _Vec3:
    x: float
    y: float
    z: float

    def add(self, other: "_Vec3") -> "_Vec3":
        return _Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def scale(self, factor: float) -> "_Vec3":
        return _Vec3(self.x * factor, self.y * factor, self.z * factor)

    def to_model(self) -> Vector3Model:
        return Vector3Model(x=self.x, y=self.y, z=self.z)


@dataclass
class _TrackState:
    track_id: UUID
    position: _Vec3
    velocity: _Vec3
    created_at: datetime
    last_update: datetime
    snr_db: float
    rcs_dbsm: float
    transponder_on: bool
    transponder_mode: TransponderModeEnum = TransponderModeEnum.OFF
    transponder_id: Optional[str] = None
    hits: int = 0
    miss_count: int = 0

    def age_seconds(self, now: datetime) -> float:
        return max((now - self.created_at).total_seconds(), 0.0)


class RadarTrackStore:
    """Maintains radar tracks using a basic alpha-beta filter."""

    def __init__(
        self,
        *,
        alpha: float = 0.6,
        beta: float = 0.1,
        max_association_distance_m: float = 12.0,
        max_radial_velocity_delta: float = 15.0,
        max_misses: int = 3,
        min_hits_to_confirm: int = 2,
        reference_snr: float = 20.0,
    ) -> None:
        self._alpha = alpha
        self._beta = beta
        self._max_association_distance = max_association_distance_m
        self._max_radial_velocity_delta = max_radial_velocity_delta
        self._max_misses = max(max_misses, 1)
        self._min_hits_to_confirm = max(min_hits_to_confirm, 1)
        self._reference_snr = max(reference_snr, 1.0)
        self._tracks: Dict[UUID, _TrackState] = {}

    def process_frame(self, frame: RadarFrameModel) -> List[RadarTrackModel]:
        """Process frame and return current set of tracks."""

        frame_ts = frame.timestamp or datetime.now(UTC)
        associations = self._associate(frame.detections, frame_ts)
        self._update_associated_tracks(associations, frame_ts)
        updated_ids = {state.track_id for _, state in associations if state}
        self._update_missed_tracks(updated_ids)
        self._spawn_new_tracks(frame.detections, associations, frame_ts)
        self._prune_lost_tracks()
        return self._serialize_tracks(frame_ts)

    def _associate(
        self, detections: List[RadarDetectionModel], frame_ts: datetime
    ) -> List[Tuple[RadarDetectionModel, Optional[_TrackState]]]:
        results: List[Tuple[RadarDetectionModel, Optional[_TrackState]]] = []
        available_tracks = list(self._tracks.values())
        for detection in detections:
            matched_state = self._find_best_match(detection, available_tracks, frame_ts)
            if matched_state is not None:
                available_tracks.remove(matched_state)
            results.append((detection, matched_state))
        return results

    def _find_best_match(
        self,
        detection: RadarDetectionModel,
        candidates: List[_TrackState],
        frame_ts: datetime,
    ) -> Optional[_TrackState]:
        if not candidates:
            return None
        det_position = _polar_to_cartesian(
            detection.range_m, detection.bearing_deg, detection.elev_deg
        )
        best_track: Optional[_TrackState] = None
        best_distance = self._max_association_distance

        for state in candidates:
            dt = max((frame_ts - state.last_update).total_seconds(), 0.05)
            predicted_position = state.position.add(state.velocity.scale(dt))
            distance = _euclidean_distance(predicted_position, det_position)
            if distance > best_distance:
                continue
            radial_delta = abs(
                detection.vr_mps
                - _project_velocity_to_radial(state.velocity, det_position)
            )
            if radial_delta > self._max_radial_velocity_delta:
                continue
            best_distance = distance
            best_track = state
        return best_track

    def _update_associated_tracks(
        self,
        associations: List[Tuple[RadarDetectionModel, Optional[_TrackState]]],
        frame_ts: datetime,
    ) -> None:
        for detection, state in associations:
            if state is None:
                continue
            dt = max((frame_ts - state.last_update).total_seconds(), 0.05)
            measured_position = _polar_to_cartesian(
                detection.range_m, detection.bearing_deg, detection.elev_deg
            )
            predicted_position = state.position.add(state.velocity.scale(dt))
            residual = _Vec3(
                measured_position.x - predicted_position.x,
                measured_position.y - predicted_position.y,
                measured_position.z - predicted_position.z,
            )

            state.position = predicted_position.add(residual.scale(self._alpha))
            unit_vector = _unit_vector(measured_position)
            measured_velocity = unit_vector.scale(detection.vr_mps)
            state.velocity = _blend_velocity(
                state.velocity, measured_velocity, self._beta
            )
            state.snr_db = (state.snr_db + detection.snr_db) / 2.0
            state.rcs_dbsm = detection.rcs_dbsm
            state.transponder_on = detection.transponder_on
            state.transponder_mode = detection.transponder_mode
            state.transponder_id = detection.transponder_id
            state.last_update = frame_ts
            state.hits += 1
            state.miss_count = 0

    def _update_missed_tracks(self, updated_ids: set[UUID]) -> None:
        for track_id, state in list(self._tracks.items()):
            if track_id in updated_ids:
                continue
            state.miss_count += 1

    def _spawn_new_tracks(
        self,
        detections: List[RadarDetectionModel],
        associations: List[Tuple[RadarDetectionModel, Optional[_TrackState]]],
        frame_ts: datetime,
    ) -> None:
        for detection, state in associations:
            if state is not None:
                continue
            position = _polar_to_cartesian(
                detection.range_m, detection.bearing_deg, detection.elev_deg
            )
            velocity = _unit_vector(position).scale(detection.vr_mps)
            track_id = uuid4()
            self._tracks[track_id] = _TrackState(
                track_id=track_id,
                position=position,
                velocity=velocity,
                created_at=frame_ts,
                last_update=frame_ts,
                snr_db=detection.snr_db,
                rcs_dbsm=detection.rcs_dbsm,
                transponder_on=detection.transponder_on,
                transponder_mode=detection.transponder_mode,
                transponder_id=detection.transponder_id,
                hits=1,
                miss_count=0,
            )

    def _prune_lost_tracks(self) -> None:
        to_delete = [
            track_id
            for track_id, state in self._tracks.items()
            if state.miss_count > self._max_misses
        ]
        for track_id in to_delete:
            del self._tracks[track_id]

    def _serialize_tracks(self, frame_ts: datetime) -> List[RadarTrackModel]:
        tracks: List[RadarTrackModel] = []
        for state in self._tracks.values():
            status = (
                RadarTrackStatusEnum.TRACKED
                if state.hits >= self._min_hits_to_confirm and state.miss_count == 0
                else RadarTrackStatusEnum.NEW
            )
            if state.miss_count > 0:
                status = RadarTrackStatusEnum.LOST

            age = state.age_seconds(frame_ts)
            quality = self._compute_quality(state)
            tracks.append(
                RadarTrackModel(
                    track_id=state.track_id,
                    object_type=ObjectTypeEnum.OBJECT_TYPE_UNSPECIFIED,
                    iff=FriendFoeEnum.UNKNOWN,
                    transponder_on=getattr(state, "transponder_on", False),
                    transponder_mode=getattr(
                        state,
                        "transponder_mode",
                        TransponderModeEnum.OFF,
                    ),
                    transponder_id=getattr(state, "transponder_id", None),
                    range_m=_cartesian_to_range(state.position),
                    bearing_deg=_cartesian_to_bearing(state.position),
                    elev_deg=_cartesian_to_elevation(state.position),
                    vr_mps=_project_velocity_to_radial(state.velocity, state.position),
                    snr_db=max(state.snr_db, 0.0),
                    rcs_dbsm=getattr(state, "rcs_dbsm", 0.0),
                    quality=quality,
                    status=status,
                    position=state.position.to_model(),
                    velocity=state.velocity.to_model(),
                    position_covariance=None,
                    velocity_covariance=None,
                    age_s=age,
                    miss_count=state.miss_count,
                    timestamp=frame_ts,
                )
            )
        return tracks

    def _compute_quality(self, state: _TrackState) -> float:
        miss_factor = max(self._max_misses - state.miss_count, 0) / self._max_misses
        snr_factor = min(state.snr_db / self._reference_snr, 1.0)
        quality = max(min(miss_factor * snr_factor, 1.0), 0.0)
        return quality


def _polar_to_cartesian(range_m: float, bearing_deg: float, elev_deg: float) -> _Vec3:
    r = max(range_m, 0.0)
    bearing_rad = math.radians(bearing_deg)
    elev_rad = math.radians(elev_deg)
    cos_elev = math.cos(elev_rad)
    x = r * cos_elev * math.cos(bearing_rad)
    y = r * cos_elev * math.sin(bearing_rad)
    z = r * math.sin(elev_rad)
    return _Vec3(x, y, z)


def _cartesian_to_range(vec: _Vec3) -> float:
    return math.sqrt(vec.x ** 2 + vec.y ** 2 + vec.z ** 2)


def _cartesian_to_bearing(vec: _Vec3) -> float:
    return math.degrees(math.atan2(vec.y, vec.x)) % 360


def _cartesian_to_elevation(vec: _Vec3) -> float:
    hyp = math.sqrt(vec.x ** 2 + vec.y ** 2)
    return math.degrees(math.atan2(vec.z, hyp))


def _euclidean_distance(a: _Vec3, b: _Vec3) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def _unit_vector(vec: _Vec3) -> _Vec3:
    norm = math.sqrt(vec.x ** 2 + vec.y ** 2 + vec.z ** 2)
    if norm == 0:
        return _Vec3(0.0, 0.0, 0.0)
    return _Vec3(vec.x / norm, vec.y / norm, vec.z / norm)


def _project_velocity_to_radial(velocity: _Vec3, position: _Vec3) -> float:
    unit = _unit_vector(position)
    return velocity.x * unit.x + velocity.y * unit.y + velocity.z * unit.z


def _blend_velocity(current: _Vec3, measured: _Vec3, beta: float) -> _Vec3:
    beta = max(min(beta, 1.0), 0.0)
    inv_beta = 1.0 - beta
    return _Vec3(
        current.x * inv_beta + measured.x * beta,
        current.y * inv_beta + measured.y * beta,
        current.z * inv_beta + measured.z * beta,
    )
