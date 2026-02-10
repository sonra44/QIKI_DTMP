"""Radar rendering pipeline with backend auto-detect and runtime fallback."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .radar_backends import (
    KittyRadarBackend,
    RadarBackend,
    RadarScene,
    RenderOutput,
    SixelRadarBackend,
    UnicodeRadarBackend,
)

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
    def __init__(self, config: RadarRenderConfig | None = None):
        self.config = config or RadarRenderConfig.from_env()
        self._unicode = UnicodeRadarBackend()
        self._kitty = KittyRadarBackend()
        self._sixel = SixelRadarBackend()
        self._active_backend = self.detect_best_backend()

    @property
    def active_backend_name(self) -> str:
        return self._active_backend.name

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

    def render_scene(self, scene: RadarScene) -> RenderOutput:
        try:
            return self._active_backend.render(scene, view=self.config.view, color=self.config.color)
        except Exception as exc:  # noqa: BLE001
            if self._active_backend.name == "unicode":
                raise
            previous = self._active_backend.name
            self._active_backend = self._unicode
            fallback = self._active_backend.render(scene, view=self.config.view, color=self.config.color)
            marker = f"[RADAR RUNTIME FALLBACK {previous}->unicode: {exc}]"
            return RenderOutput(
                backend=fallback.backend,
                lines=[marker, *fallback.lines],
                used_runtime_fallback=True,
            )


def render_radar_scene(scene: RadarScene, *, pipeline: RadarPipeline | None = None) -> RenderOutput:
    active = pipeline or RadarPipeline()
    return active.render_scene(scene)
