"""Local world model for the Q-Core agent."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID, uuid4

from qiki.shared.models.core import SensorData, SensorTypeEnum
from qiki.shared.models.radar import FriendFoeEnum, RadarTrackModel, RadarTrackStatusEnum

from qiki.services.q_core_agent.core.guard_table import GuardEvaluationResult, GuardTable
from qiki.services.q_core_agent.core.metrics import publish_world_model_metrics


class WorldModel:
    """Maintains the agent-centric view of the environment."""

    def __init__(self, guard_table: GuardTable):
        self._guard_table = guard_table
        self._radar_tracks: Dict[str, RadarTrackModel] = {}
        self._frame_derived_track_ids: Set[str] = set()
        self._guard_results: List[GuardEvaluationResult] = []
        self._active_guard_keys: Set[Tuple[str, str]] = set()
        self._active_warning_keys: Set[Tuple[str, str]] = set()

    def ingest_sensor_data(self, sensor_data: SensorData) -> None:
        """Update world model state from incoming sensor data."""

        if sensor_data.sensor_type != SensorTypeEnum.RADAR:
            return

        track = sensor_data.radar_track
        if track is not None:
            track_id = str(track.track_id)

            if track.status == RadarTrackStatusEnum.LOST:
                self._radar_tracks.pop(track_id, None)
                self._frame_derived_track_ids.discard(track_id)
            else:
                self._radar_tracks[track_id] = track

            self._recalculate_guards()
            return

        frame = sensor_data.radar_frame
        if frame is None:
            return

        updated_tracks: Dict[str, RadarTrackModel] = {}
        remaining_candidates: Dict[str, RadarTrackModel] = {
            track_id: self._radar_tracks[track_id]
            for track_id in self._frame_derived_track_ids
            if track_id in self._radar_tracks
        }
        for index, detection in enumerate(frame.detections):
            matched_track_id = self._match_existing_frame_track_id(detection=detection, existing_tracks=remaining_candidates)
            if matched_track_id:
                remaining_candidates.pop(matched_track_id, None)
            track = self._track_from_detection(
                sensor_id=sensor_data.sensor_id,
                index=index,
                detection=detection,
                existing_track_id=(UUID(matched_track_id) if matched_track_id else None),
            )
            updated_tracks[str(track.track_id)] = track

        previous_derived_track_ids = set(self._frame_derived_track_ids)
        for track_id in previous_derived_track_ids:
            self._radar_tracks.pop(track_id, None)
        self._radar_tracks.update(updated_tracks)
        self._frame_derived_track_ids = set(updated_tracks.keys())

        if updated_tracks or previous_derived_track_ids:
            self._recalculate_guards()

    def _recalculate_guards(self) -> None:
        evaluations = self._guard_table.evaluate_tracks(self._radar_tracks.values())

        deduped: Dict[Tuple[str, str], GuardEvaluationResult] = {}
        for result in evaluations:
            key = self._guard_key(result)
            current = deduped.get(key)
            if current is None or result.severity_weight > current.severity_weight:
                deduped[key] = result

        guard_results = sorted(
            deduped.values(),
            key=self._sort_key,
            reverse=True,
        )
        self._guard_results = guard_results

        active_keys = set(deduped.keys())
        warning_keys = {key for key, value in deduped.items() if value.severity == "warning"}
        new_warning_events = len(warning_keys - self._active_warning_keys)

        publish_world_model_metrics(
            active_tracks=len(self._radar_tracks),
            guard_results=self._guard_results,
            new_warning_events=new_warning_events,
        )

        self._active_guard_keys = active_keys
        self._active_warning_keys = warning_keys

    def active_radar_tracks(self) -> List[RadarTrackModel]:
        return list(self._radar_tracks.values())

    def guard_results(self) -> List[GuardEvaluationResult]:
        return list(self._guard_results)

    def snapshot(self) -> dict:
        return {
            "active_track_count": len(self._radar_tracks),
            "critical_guard_count": sum(1 for result in self._guard_results if result.severity == "critical"),
            "warning_guard_count": sum(1 for result in self._guard_results if result.severity == "warning"),
            "radar_tracks": [self._snapshot_track_payload(track) for track in self._radar_tracks.values()],
            "guard_results": [result.model_dump() for result in self._guard_results],
        }

    def most_critical_guard(self) -> Optional[GuardEvaluationResult]:
        if not self._guard_results:
            return None
        return self._guard_results[0]

    @staticmethod
    def _guard_key(result: GuardEvaluationResult) -> Tuple[str, str]:
        return result.rule_id, result.track_id

    @staticmethod
    def _sort_key(result: GuardEvaluationResult) -> Tuple[int, float, float]:
        return (
            result.severity_weight,
            -result.range_m,
            result.quality,
        )

    @staticmethod
    def _bearing_delta_deg(left: float, right: float) -> float:
        delta = abs(left - right) % 360.0
        return min(delta, 360.0 - delta)

    @classmethod
    def _match_existing_frame_track_id(
        cls,
        *,
        detection,
        existing_tracks: Dict[str, RadarTrackModel],  # noqa: ANN001
    ) -> str | None:
        best_track_id: str | None = None
        best_score: Tuple[float, float, float] | None = None
        for track_id, track in existing_tracks.items():
            try:
                range_delta = abs(float(track.range_m) - float(detection.range_m))
                bearing_delta = cls._bearing_delta_deg(float(track.bearing_deg), float(detection.bearing_deg))
                elev_delta = abs(float(track.elev_deg) - float(detection.elev_deg))
                radial_delta = abs(float(track.vr_mps) - float(detection.vr_mps))
            except Exception:
                continue
            if range_delta > 2500.0 or bearing_delta > 12.0 or elev_delta > 8.0 or radial_delta > 250.0:
                continue
            score = (range_delta, bearing_delta + elev_delta, radial_delta)
            if best_score is None or score < best_score:
                best_score = score
                best_track_id = track_id
        return best_track_id

    @staticmethod
    def _track_from_detection(
        *,
        sensor_id: str,
        index: int,
        detection,
        existing_track_id: UUID | None = None,
    ) -> RadarTrackModel:  # noqa: ANN001
        quality = 1.0 if detection.transponder_id else 0.5
        return RadarTrackModel(
            track_id=existing_track_id or uuid4(),
            iff=FriendFoeEnum.UNKNOWN,
            transponder_on=bool(detection.transponder_on),
            transponder_mode=detection.transponder_mode,
            transponder_id=detection.transponder_id,
            quality=quality,
            status=RadarTrackStatusEnum.TRACKED,
            range_m=detection.range_m,
            bearing_deg=detection.bearing_deg,
            elev_deg=detection.elev_deg,
            vr_mps=detection.vr_mps,
            snr_db=detection.snr_db,
            rcs_dbsm=detection.rcs_dbsm,
        )

    @staticmethod
    def _snapshot_track_payload(track: RadarTrackModel) -> dict:
        payload = track.model_dump()
        visible_signature = str(track.transponder_id or "").strip() or None
        payload.update(
            {
                # Runtime object continuity is owned by the frame-derived track id.
                "object_identity": str(track.track_id),
                # Visible signature is observation-facing and may mutate without object replacement.
                "visible_signature": visible_signature,
            }
        )
        return payload
