from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


def _public_designator(track: dict[str, Any] | None) -> str:
    if not isinstance(track, dict):
        return ""
    return str(track.get("transponder_id") or track.get("id") or track.get("callsign") or "").strip()


def pick_public_target_from_tracks(
    tracks: Iterable[dict[str, Any] | Any],
    *,
    require_non_spoof: bool = False,
) -> tuple[str, dict[str, Any]]:
    for track in tracks:
        if not isinstance(track, dict):
            continue
        designator = _public_designator(track)
        if not designator:
            continue
        if require_non_spoof and designator.upper().startswith("SPOOF-"):
            continue
        return designator, track
    raise AssertionError("no public track with a usable visible designator is available")


def pick_initial_target_designator(
    *,
    orion_tracks: Iterable[dict[str, Any] | Any],
    require_non_spoof: bool = False,
    qcore_fallback: Callable[[], tuple[str, dict[str, Any]]] | None = None,
) -> tuple[str, dict[str, Any], str]:
    try:
        designator, track = pick_public_target_from_tracks(
            orion_tracks,
            require_non_spoof=require_non_spoof,
        )
        return designator, track, "orion_live_radar_cache"
    except AssertionError:
        if qcore_fallback is None:
            raise
    designator, track = qcore_fallback()
    return designator, track, "q_core_world_snapshot_fallback"
