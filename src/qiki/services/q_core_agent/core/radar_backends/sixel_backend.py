"""SIXEL backend for radar pipeline."""

from __future__ import annotations

import os

from .base import RadarBackend, RadarScene, RenderOutput
from .bitmap_common import image_to_sixel_text, scene_to_image
from qiki.services.q_core_agent.core.radar_render_policy import RadarRenderPlan
from qiki.services.q_core_agent.core.radar_view_state import RadarViewState


class SixelRadarBackend(RadarBackend):
    name = "sixel"

    def is_supported(self) -> bool:
        if os.getenv("QIKI_FORCE_SIXEL_SUPPORTED", "").strip() == "1":
            return True
        term = os.getenv("TERM", "").lower()
        return "sixel" in term

    def render(
        self,
        scene: RadarScene,
        *,
        view_state: RadarViewState,
        color: bool,
        render_plan: RadarRenderPlan | None = None,
    ) -> RenderOutput:
        if not self.is_supported():
            raise RuntimeError("SIXEL backend is unsupported in this terminal")
        image = scene_to_image(scene, view_state=view_state, color=color, render_plan=render_plan)
        sixel = image_to_sixel_text(image)
        lines = [
            "[SIXEL BITMAP FRAME]",
            sixel,
            f"backend=sixel size={image.width}x{image.height}",
        ]
        return RenderOutput(backend=self.name, lines=lines, plan=render_plan, stats=(render_plan.stats if render_plan else None))
