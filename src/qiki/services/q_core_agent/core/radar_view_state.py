"""State model for radar view controls."""

from __future__ import annotations

import os
from dataclasses import dataclass

_ALLOWED_VIEWS = {"top", "side", "front", "iso"}


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

    @classmethod
    def from_env(cls) -> "RadarViewState":
        view = os.getenv("RADAR_VIEW", "top").strip().lower() or "top"
        if view not in _ALLOWED_VIEWS:
            view = "top"
        color_raw = os.getenv("RADAR_COLOR", "1").strip().lower()
        color_enabled = color_raw not in {"0", "false", "no", "off"}
        return cls(view=view, color_enabled=color_enabled)

