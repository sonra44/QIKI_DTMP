"""Backend-agnostic radar render policy (LOD + anti-clutter)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .radar_view_state import RadarOverlayState, RadarViewState


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


@dataclass(frozen=True)
class RadarRenderStats:
    frame_time_ms: float = 0.0
    targets_count: int = 0
    clutter_on: bool = False
    clutter_reason: str = ""
    dropped_overlays: tuple[str, ...] = ()
    lod_level: int = 0
    bitmap_scale: float = 1.0


@dataclass(frozen=True)
class RadarRenderPlan:
    lod_level: int
    draw_grid: bool
    draw_range_rings: bool
    draw_vectors: bool
    draw_trails: bool
    draw_labels: bool
    draw_selection_highlight: bool
    clutter_on: bool
    clutter_reason: str
    dropped_overlays: tuple[str, ...]
    bitmap_scale: float
    targets_count: int
    stats: RadarRenderStats


@dataclass(frozen=True)
class RadarRenderPolicy:
    lod_vector_zoom: float = 1.2
    lod_label_zoom: float = 1.5
    lod_detail_zoom: float = 2.0
    clutter_targets_max: int = 30
    frame_budget_ms: float = 80.0
    trail_len: int = 20
    bitmap_scale: float = 1.0

    @classmethod
    def from_env(cls) -> "RadarRenderPolicy":
        return cls(
            lod_vector_zoom=_env_float("RADAR_LOD_VECTOR_ZOOM", 1.2),
            lod_label_zoom=_env_float("RADAR_LOD_LABEL_ZOOM", 1.5),
            lod_detail_zoom=_env_float("RADAR_LOD_DETAIL_ZOOM", 2.0),
            clutter_targets_max=max(1, _env_int("RADAR_CLUTTER_TARGETS_MAX", 30)),
            frame_budget_ms=max(1.0, _env_float("RADAR_FRAME_BUDGET_MS", 80.0)),
            trail_len=max(1, _env_int("RADAR_TRAIL_LEN", 20)),
            bitmap_scale=max(0.25, _env_float("RADAR_BITMAP_SCALE", 1.0)),
        )

    def lod_level(self, zoom: float) -> int:
        if zoom < self.lod_vector_zoom:
            return 0
        if zoom < self.lod_label_zoom:
            return 1
        if zoom < self.lod_detail_zoom:
            return 2
        return 3

    def build_plan(
        self,
        *,
        view_state: RadarViewState,
        targets_count: int,
        frame_time_ms: float,
    ) -> RadarRenderPlan:
        lod = self.lod_level(view_state.zoom)
        overlays: RadarOverlayState = view_state.overlays
        draw_grid = view_state.overlays_enabled and overlays.grid
        draw_range_rings = view_state.overlays_enabled and overlays.range_rings
        draw_vectors = view_state.overlays_enabled and overlays.vectors and lod >= 1
        draw_labels = view_state.overlays_enabled and overlays.labels and lod >= 2
        draw_trails = view_state.overlays_enabled and overlays.trails
        draw_selection_highlight = overlays.selection_highlight
        dropped: list[str] = []
        clutter_reason = ""
        clutter_on = False
        bitmap_scale = self.bitmap_scale

        if targets_count > self.clutter_targets_max:
            clutter_on = True
            clutter_reason = "TARGET_OVERLOAD"
        if frame_time_ms > self.frame_budget_ms:
            clutter_on = True
            clutter_reason = clutter_reason or "FRAME_BUDGET_EXCEEDED"

        if clutter_on:
            if draw_labels:
                draw_labels = False
                dropped.append("labels")
            if draw_trails:
                draw_trails = False
                dropped.append("trails")
            if draw_vectors:
                draw_vectors = False
                dropped.append("vectors")
            bitmap_scale = min(bitmap_scale, 0.75)

        if lod == 0:
            if draw_labels:
                draw_labels = False
                dropped.append("labels_lod")
            if draw_vectors:
                draw_vectors = False
                dropped.append("vectors_lod")
            if draw_trails:
                draw_trails = False
                dropped.append("trails_lod")
        elif lod == 1:
            if draw_labels:
                draw_labels = False
                dropped.append("labels_lod")

        stats = RadarRenderStats(
            frame_time_ms=frame_time_ms,
            targets_count=targets_count,
            clutter_on=clutter_on,
            clutter_reason=clutter_reason,
            dropped_overlays=tuple(dropped),
            lod_level=lod,
            bitmap_scale=bitmap_scale,
        )
        return RadarRenderPlan(
            lod_level=lod,
            draw_grid=draw_grid,
            draw_range_rings=draw_range_rings,
            draw_vectors=draw_vectors,
            draw_trails=draw_trails,
            draw_labels=draw_labels,
            draw_selection_highlight=draw_selection_highlight,
            clutter_on=clutter_on,
            clutter_reason=clutter_reason,
            dropped_overlays=tuple(dropped),
            bitmap_scale=bitmap_scale,
            targets_count=targets_count,
            stats=stats,
        )
