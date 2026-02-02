"""Local world model for the Q-Core agent."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from qiki.shared.models.core import SensorData, SensorTypeEnum
from qiki.shared.models.radar import RadarTrackModel, RadarTrackStatusEnum

from qiki.services.q_core_agent.core.guard_table import GuardEvaluationResult, GuardTable
from qiki.services.q_core_agent.core.metrics import publish_world_model_metrics


class WorldModel:
    """Maintains the agent-centric view of the environment."""

    def __init__(self, guard_table: GuardTable):
        self._guard_table = guard_table
        self._radar_tracks: Dict[str, RadarTrackModel] = {}
        self._guard_results: List[GuardEvaluationResult] = []
        self._active_guard_keys: Set[Tuple[str, str]] = set()
        self._active_warning_keys: Set[Tuple[str, str]] = set()

    def ingest_sensor_data(self, sensor_data: SensorData) -> None:
        """Update world model state from incoming sensor data."""

        if sensor_data.sensor_type != SensorTypeEnum.RADAR:
            return

        track = sensor_data.radar_track
        if track is None:
            return

        track_id = str(track.track_id)

        if track.status == RadarTrackStatusEnum.LOST:
            self._radar_tracks.pop(track_id, None)
        else:
            self._radar_tracks[track_id] = track

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
            "radar_tracks": [track.model_dump() for track in self._radar_tracks.values()],
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
