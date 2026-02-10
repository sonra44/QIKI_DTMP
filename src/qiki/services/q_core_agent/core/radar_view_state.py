"""State model for radar view controls."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

_ALLOWED_VIEWS = {"top", "side", "front", "iso"}


@dataclass(frozen=True)
class RadarOverlayState:
    grid: bool = True
    range_rings: bool = True
    vectors: bool = True
    trails: bool = True
    labels: bool = True
    selection_highlight: bool = True


@dataclass(frozen=True)
class RadarInspectorState:
    mode: str = "off"  # off | on | pinned
    pinned_target_id: str | None = None
    details_level: int = 1


@dataclass(frozen=True)
class RadarViewState:
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    rot_yaw: float = 0.0
    rot_pitch: float = 0.0
    view: str = "top"
    selected_target_id: str | None = None
    overlays_enabled: bool = True
    color_enabled: bool = True
    overlays: RadarOverlayState = field(default_factory=RadarOverlayState)
    inspector: RadarInspectorState = field(default_factory=RadarInspectorState)

    @classmethod
    def from_env(cls) -> "RadarViewState":
        view = os.getenv("RADAR_VIEW", "top").strip().lower() or "top"
        if view not in _ALLOWED_VIEWS:
            view = "top"
        color_raw = os.getenv("RADAR_COLOR", "1").strip().lower()
        color_enabled = color_raw not in {"0", "false", "no", "off"}
        return cls(view=view, color_enabled=color_enabled)
