"""Per-track radar trail storage for readability overlays."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque

from .radar_backends.base import RadarPoint, RadarScene


class RadarTrailStore:
    def __init__(self, max_len: int = 20):
        self.max_len = max(1, int(max_len))
        self._tracks: dict[str, Deque[RadarPoint]] = defaultdict(lambda: deque(maxlen=self.max_len))

    def update_from_scene(self, scene: RadarScene) -> None:
        if not scene.ok:
            # Honest no-data: do not extend trails.
            return
        for idx, point in enumerate(scene.points):
            track_id = str(point.metadata.get("target_id") or point.metadata.get("id") or f"target-{idx}")
            self._tracks[track_id].append(point)

    def get_trail(self, track_id: str) -> list[RadarPoint]:
        if not track_id:
            return []
        return list(self._tracks.get(track_id, ()))

    def get_all(self) -> dict[str, list[RadarPoint]]:
        return {track_id: list(points) for track_id, points in self._tracks.items()}
