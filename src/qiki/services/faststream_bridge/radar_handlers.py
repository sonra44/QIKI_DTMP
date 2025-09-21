from __future__ import annotations

from time import perf_counter
from datetime import UTC, datetime
from typing import List

from uuid import uuid4

from qiki.shared.models.radar import (
    RadarFrameModel,
    RadarTrackModel,
    ObjectTypeEnum,
    FriendFoeEnum,
    RadarTrackStatusEnum,
)
from qiki.services.faststream_bridge.metrics import observe_frame
from qiki.services.faststream_bridge.radar_track_store import RadarTrackStore


_TRACK_STORE = RadarTrackStore()


def frame_to_track(frame: RadarFrameModel) -> RadarTrackModel:
    """Stateful frame-to-track conversion using RadarTrackStore."""

    start = perf_counter()
    tracks = _TRACK_STORE.process_frame(frame)
    duration_ms = (perf_counter() - start) * 1000.0
    observe_frame(duration_ms, len(tracks))

    if not tracks:
        return _empty_track()

    return _select_best_track(tracks)


def reset_track_store() -> None:
    """Reset global track store (primarily for tests)."""

    global _TRACK_STORE
    _TRACK_STORE = RadarTrackStore()


def _select_best_track(tracks: List[RadarTrackModel]) -> RadarTrackModel:
    return max(
        tracks,
        key=lambda track: (
            track.quality,
            int(track.status != RadarTrackStatusEnum.LOST),
            -track.range_m,
        ),
    )


def _empty_track() -> RadarTrackModel:
    now = datetime.now(UTC)
    return RadarTrackModel(
        track_id=uuid4(),
        object_type=ObjectTypeEnum.OBJECT_TYPE_UNSPECIFIED,
        iff=FriendFoeEnum.UNKNOWN,
        transponder_on=False,
        quality=0.0,
        status=RadarTrackStatusEnum.LOST,
        range_m=0.0,
        bearing_deg=0.0,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=0.0,
        rcs_dbsm=0.0,
        position=None,
        velocity=None,
        position_covariance=None,
        velocity_covariance=None,
        age_s=0.0,
        miss_count=0,
        timestamp=now,
    )
