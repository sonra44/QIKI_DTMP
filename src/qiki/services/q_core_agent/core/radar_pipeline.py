"""Radar rendering pipeline with backend auto-detect and runtime fallback."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from .radar_backends import (
    KittyRadarBackend,
    RadarBackend,
    RadarScene,
    RenderOutput,
    SixelRadarBackend,
    UnicodeRadarBackend,
)
from .event_store import EventStore, TruthState
from .radar_render_policy import DegradationState, RadarRenderPlan, RadarRenderPolicy
from .radar_trail_store import RadarTrailStore
from .radar_view_state import RadarViewState

_ALLOWED_VIEWS = {"top", "side", "front", "iso"}


@dataclass(frozen=True)
class RadarRenderConfig:
    renderer: str
    view: str
    fps_max: int
    color: bool

    @classmethod
    def from_env(cls) -> "RadarRenderConfig":
        renderer = os.getenv("RADAR_RENDERER", "auto").strip().lower() or "auto"
        view = os.getenv("RADAR_VIEW", "top").strip().lower() or "top"
        if view not in _ALLOWED_VIEWS:
            view = "top"
        try:
            fps_max = max(1, int(os.getenv("RADAR_FPS_MAX", "10")))
        except Exception:
            fps_max = 10
        color_raw = os.getenv("RADAR_COLOR", "1").strip().lower()
        color = color_raw not in {"0", "false", "no", "off"}
        return cls(renderer=renderer, view=view, fps_max=fps_max, color=color)


class RadarPipeline:
    def __init__(self, config: RadarRenderConfig | None = None, *, event_store: EventStore | None = None):
        self.config = config or RadarRenderConfig.from_env()
        telemetry_raw = os.getenv("RADAR_TELEMETRY", "1").strip().lower()
        self.telemetry_enabled = telemetry_raw not in {"0", "false", "no", "off"}
        self.event_store = event_store
        self.view_state = RadarViewState.from_env()
        self.render_policy = RadarRenderPolicy.from_env()
        self.trail_store = RadarTrailStore(max_len=self.render_policy.trail_len)
        self._last_frame_time_ms = 0.0
        self._degradation_state = DegradationState(last_scale=self.render_policy.bitmap_scales[0])
        if self.config.view in _ALLOWED_VIEWS:
            self.view_state = RadarViewState(
                zoom=self.view_state.zoom,
                pan_x=self.view_state.pan_x,
                pan_y=self.view_state.pan_y,
                rot_yaw=self.view_state.rot_yaw,
                rot_pitch=self.view_state.rot_pitch,
                view=self.config.view,
                selected_target_id=self.view_state.selected_target_id,
                overlays_enabled=self.view_state.overlays_enabled,
                color_enabled=self.config.color and self.view_state.color_enabled,
                overlays=self.view_state.overlays,
                inspector=self.view_state.inspector,
            )
        self._unicode = UnicodeRadarBackend()
        self._kitty = KittyRadarBackend()
        self._sixel = SixelRadarBackend()
        self._active_backend = self.detect_best_backend()

    @property
    def active_backend_name(self) -> str:
        return self._active_backend.name

    def build_render_plan(self, scene: RadarScene, *, view_state: RadarViewState | None = None) -> RadarRenderPlan:
        active_view_state = view_state or self.view_state
        plan, next_state = self.render_policy.build_plan(
            view_state=active_view_state,
            targets_count=len(scene.points),
            frame_time_ms=self._last_frame_time_ms,
            backend_name=self._active_backend.name,
            degradation_state=self._degradation_state,
            now_ts=time.monotonic(),
        )
        self._degradation_state = next_state
        return plan

    def detect_best_backend(self) -> RadarBackend:
        requested = self.config.renderer
        if requested == "unicode":
            return self._unicode
        if requested == "kitty":
            if self._kitty.is_supported():
                return self._kitty
            raise RuntimeError("RADAR_RENDERER=kitty requested but Kitty backend is unsupported")
        if requested == "sixel":
            if self._sixel.is_supported():
                return self._sixel
            raise RuntimeError("RADAR_RENDERER=sixel requested but SIXEL backend is unsupported")

        # auto mode: prefer bitmap upgrades only when support is clear.
        if self._kitty.is_supported():
            return self._kitty
        if self._sixel.is_supported():
            return self._sixel
        return self._unicode

    def render_scene(self, scene: RadarScene, *, view_state: RadarViewState | None = None) -> RenderOutput:
        active_view_state = view_state or self.view_state
        self.trail_store.update_from_scene(scene)
        scene_with_trails = RadarScene(
            ok=scene.ok,
            reason=scene.reason,
            truth_state=scene.truth_state,
            is_fallback=scene.is_fallback,
            points=scene.points,
            trails={k: v for k, v in self.trail_store.get_all().items()},
        )
        plan = self.build_render_plan(scene_with_trails, view_state=active_view_state)
        render_start = time.monotonic()
        try:
            output = self._active_backend.render(
                scene_with_trails,
                view_state=active_view_state,
                color=(self.config.color and active_view_state.color_enabled),
                render_plan=plan,
            )
            self._last_frame_time_ms = (time.monotonic() - render_start) * 1000.0
            self._append_render_tick_event(scene_with_trails, output)
            return output
        except Exception as exc:  # noqa: BLE001
            if self._active_backend.name == "unicode":
                raise
            previous = self._active_backend.name
            self._active_backend = self._unicode
            fallback = self._active_backend.render(
                scene_with_trails,
                view_state=active_view_state,
                color=(self.config.color and active_view_state.color_enabled),
                render_plan=plan,
            )
            marker = f"[RADAR RUNTIME FALLBACK {previous}->unicode: {exc}]"
            self._last_frame_time_ms = (time.monotonic() - render_start) * 1000.0
            output = RenderOutput(
                backend=fallback.backend,
                lines=[marker, *fallback.lines],
                used_runtime_fallback=True,
                plan=plan,
                stats=plan.stats,
            )
            self._append_render_tick_event(scene_with_trails, output)
            return output

    def _append_render_tick_event(self, scene: RadarScene, output: RenderOutput) -> None:
        if not self.telemetry_enabled or self.event_store is None:
            return
        stats = output.stats
        plan = output.plan
        if stats is None or plan is None:
            return
        truth_state = TruthState.OK
        normalized = str(scene.truth_state or "").upper()
        if normalized == TruthState.NO_DATA.value:
            truth_state = TruthState.NO_DATA
        elif normalized == TruthState.FALLBACK.value:
            truth_state = TruthState.FALLBACK
        elif normalized not in {TruthState.OK.value, TruthState.NO_DATA.value, TruthState.FALLBACK.value}:
            truth_state = TruthState.INVALID
        reasons = list(stats.clutter_reasons)
        self.event_store.append_new(
            subsystem="RADAR",
            event_type="RADAR_RENDER_TICK",
            payload={
                "frame_ms": float(stats.frame_time_ms),
                "fps_cap": int(self.config.fps_max),
                "targets_count": int(stats.targets_count),
                "lod_level": int(stats.lod_level),
                "degradation_level": int(stats.degradation_level),
                "bitmap_scale": float(stats.bitmap_scale),
                "dropped_overlays": list(stats.dropped_overlays),
                "clutter_reasons": reasons,
                "backend": output.backend,
            },
            truth_state=truth_state,
            reason=",".join(reasons) if reasons else "OK",
        )


def render_radar_scene(scene: RadarScene, *, pipeline: RadarPipeline | None = None) -> RenderOutput:
    active = pipeline or RadarPipeline()
    return active.render_scene(scene)
