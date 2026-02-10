"""Backend-agnostic radar render policy (LOD + anti-clutter)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

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
    clutter_reasons: tuple[str, ...] = ()
    dropped_overlays: tuple[str, ...] = ()
    lod_level: int = 0
    bitmap_scale: float = 1.0
    degradation_level: int = 0


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
    clutter_reasons: tuple[str, ...]
    dropped_overlays: tuple[str, ...]
    bitmap_scale: float
    degradation_level: int
    targets_count: int
    stats: RadarRenderStats


class ClutterReason(str, Enum):
    TARGET_OVERLOAD = "TARGET_OVERLOAD"
    FRAME_BUDGET_EXCEEDED = "FRAME_BUDGET_EXCEEDED"
    LOW_CAPABILITY_BACKEND = "LOW_CAPABILITY_BACKEND"
    MANUAL_CLUTTER_LOCK = "MANUAL_CLUTTER_LOCK"


@dataclass(frozen=True)
class DegradationState:
    current_level: int = 0
    last_change_ts: float = 0.0
    consecutive_budget_violations: int = 0
    consecutive_budget_ok: int = 0
    last_scale: float = 1.0


@dataclass(frozen=True)
class RadarRenderPolicy:
    lod_vector_zoom: float = 1.2
    lod_label_zoom: float = 1.5
    lod_detail_zoom: float = 2.0
    clutter_targets_max: int = 30
    frame_budget_ms: float = 80.0
    trail_len: int = 20
    bitmap_scales: tuple[float, ...] = (1.0, 0.75, 0.5, 0.35)
    degrade_cooldown_ms: int = 800
    recovery_confirm_frames: int = 6
    degrade_confirm_frames: int = 2
    manual_clutter_lock: bool = False

    @staticmethod
    def _parse_bitmap_scales(raw: str) -> tuple[float, ...]:
        parsed: list[float] = []
        for item in raw.split(","):
            if item.strip() == "":
                continue
            try:
                value = float(item.strip())
            except Exception:
                continue
            if value <= 0.0:
                continue
            parsed.append(value)
        if not parsed:
            return (1.0, 0.75, 0.5, 0.35)
        return tuple(parsed)

    @classmethod
    def from_env(cls) -> "RadarRenderPolicy":
        bitmap_scales = cls._parse_bitmap_scales(os.getenv("RADAR_BITMAP_SCALES", "1.0,0.75,0.5,0.35"))
        manual_lock = os.getenv("RADAR_MANUAL_CLUTTER_LOCK", "0").strip().lower() in {"1", "true", "yes", "on"}
        return cls(
            lod_vector_zoom=_env_float("RADAR_LOD_VECTOR_ZOOM", 1.2),
            lod_label_zoom=_env_float("RADAR_LOD_LABEL_ZOOM", 1.5),
            lod_detail_zoom=_env_float("RADAR_LOD_DETAIL_ZOOM", 2.0),
            clutter_targets_max=max(1, _env_int("RADAR_CLUTTER_TARGETS_MAX", 30)),
            frame_budget_ms=max(1.0, _env_float("RADAR_FRAME_BUDGET_MS", 80.0)),
            trail_len=max(1, _env_int("RADAR_TRAIL_LEN", 20)),
            bitmap_scales=bitmap_scales,
            degrade_cooldown_ms=max(0, _env_int("RADAR_DEGRADE_COOLDOWN_MS", 800)),
            recovery_confirm_frames=max(1, _env_int("RADAR_RECOVERY_CONFIRM_FRAMES", 6)),
            degrade_confirm_frames=max(1, _env_int("RADAR_DEGRADE_CONFIRM_FRAMES", 2)),
            manual_clutter_lock=manual_lock,
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
        backend_name: str = "unicode",
        degradation_state: DegradationState | None = None,
        now_ts: float | None = None,
    ) -> tuple[RadarRenderPlan, DegradationState]:
        active_state = degradation_state or DegradationState(last_scale=self.bitmap_scales[0])
        now = float(now_ts if now_ts is not None else 0.0)
        lod = self.lod_level(view_state.zoom)
        overlays: RadarOverlayState = view_state.overlays
        draw_grid = view_state.overlays_enabled and overlays.grid
        draw_range_rings = view_state.overlays_enabled and overlays.range_rings
        draw_vectors = view_state.overlays_enabled and overlays.vectors and lod >= 1
        draw_labels = view_state.overlays_enabled and overlays.labels and lod >= 2
        draw_trails = view_state.overlays_enabled and overlays.trails
        draw_selection_highlight = overlays.selection_highlight
        dropped: list[str] = []
        reasons: list[str] = []
        if targets_count > self.clutter_targets_max:
            reasons.append(ClutterReason.TARGET_OVERLOAD.value)
        if frame_time_ms > self.frame_budget_ms:
            reasons.append(ClutterReason.FRAME_BUDGET_EXCEEDED.value)
        if self.manual_clutter_lock:
            reasons.append(ClutterReason.MANUAL_CLUTTER_LOCK.value)

        trigger_active = bool(reasons)
        violations = active_state.consecutive_budget_violations + 1 if trigger_active else 0
        ok_frames = active_state.consecutive_budget_ok + 1 if not trigger_active else 0
        current_level = active_state.current_level
        elapsed_ms = (now - active_state.last_change_ts) * 1000.0 if active_state.last_change_ts > 0.0 and now > 0.0 else 10_000.0
        can_change = elapsed_ms >= float(self.degrade_cooldown_ms)
        max_level = max(0, len(self.bitmap_scales) - 1)
        if trigger_active and can_change and violations >= self.degrade_confirm_frames and current_level < max_level:
            current_level += 1
            violations = 0
            ok_frames = 0
            last_change_ts = now
        elif (not trigger_active) and can_change and ok_frames >= self.recovery_confirm_frames and current_level > 0:
            current_level -= 1
            violations = 0
            ok_frames = 0
            last_change_ts = now
        else:
            last_change_ts = active_state.last_change_ts

        if current_level > 0 and backend_name == "unicode":
            reasons.append(ClutterReason.LOW_CAPABILITY_BACKEND.value)

        clutter_on = current_level > 0
        if current_level >= 1 and draw_labels:
            draw_labels = False
            dropped.append("labels")
        if current_level >= 2 and draw_trails:
            draw_trails = False
            dropped.append("trails")
        if current_level >= 3 and draw_vectors:
            draw_vectors = False
            dropped.append("vectors")

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

        unique_reasons: list[str] = []
        for reason in reasons:
            if reason not in unique_reasons:
                unique_reasons.append(reason)
        bitmap_scale = self.bitmap_scales[min(current_level, len(self.bitmap_scales) - 1)]

        next_state = DegradationState(
            current_level=current_level,
            last_change_ts=last_change_ts,
            consecutive_budget_violations=violations,
            consecutive_budget_ok=ok_frames,
            last_scale=bitmap_scale,
        )

        stats = RadarRenderStats(
            frame_time_ms=frame_time_ms,
            targets_count=targets_count,
            clutter_on=clutter_on,
            clutter_reasons=tuple(unique_reasons),
            dropped_overlays=tuple(dropped),
            lod_level=lod,
            bitmap_scale=bitmap_scale,
            degradation_level=current_level,
        )
        plan = RadarRenderPlan(
            lod_level=lod,
            draw_grid=draw_grid,
            draw_range_rings=draw_range_rings,
            draw_vectors=draw_vectors,
            draw_trails=draw_trails,
            draw_labels=draw_labels,
            draw_selection_highlight=draw_selection_highlight,
            clutter_on=clutter_on,
            clutter_reasons=tuple(unique_reasons),
            dropped_overlays=tuple(dropped),
            bitmap_scale=bitmap_scale,
            degradation_level=current_level,
            targets_count=targets_count,
            stats=stats,
        )
        return plan, next_state
