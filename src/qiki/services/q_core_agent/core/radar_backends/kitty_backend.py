"""Kitty graphics backend for radar pipeline."""

from __future__ import annotations

import base64
import os

from .base import RadarBackend, RadarScene, RenderOutput
from .bitmap_common import image_to_png_bytes, scene_to_image
from qiki.services.q_core_agent.core.radar_render_policy import RadarRenderPlan
from qiki.services.q_core_agent.core.radar_view_state import RadarViewState


class KittyRadarBackend(RadarBackend):
    name = "kitty"

    def is_supported(self) -> bool:
        if os.getenv("QIKI_FORCE_KITTY_SUPPORTED", "").strip() == "1":
            return True
        # Conservative guard: tmux/SSH often break terminal-graphics passthrough.
        # If capability is uncertain, auto mode must prefer Unicode baseline.
        if os.getenv("TMUX") and os.getenv("QIKI_ALLOW_TMUX_BITMAP", "").strip() != "1":
            return False
        if os.getenv("SSH_CONNECTION") and os.getenv("QIKI_ALLOW_SSH_BITMAP", "").strip() != "1":
            return False
        term = os.getenv("TERM", "").lower()
        if "kitty" in term:
            return True
        # Conservative mode: explicit kitty window id also indicates support.
        return bool(os.getenv("KITTY_WINDOW_ID", "").strip())

    def render(
        self,
        scene: RadarScene,
        *,
        view_state: RadarViewState,
        color: bool,
        render_plan: RadarRenderPlan | None = None,
    ) -> RenderOutput:
        if not self.is_supported():
            raise RuntimeError("Kitty backend is unsupported in this terminal")
        image = scene_to_image(scene, view_state=view_state, color=color, render_plan=render_plan)
        png_bytes = image_to_png_bytes(image)
        payload = base64.b64encode(png_bytes).decode("ascii")
        # Kitty graphics protocol transfer (direct payload in single chunk).
        escape = f"\x1b_Gf=100,t=d,m=0;{payload}\x1b\\"
        lines = [
            "[KITTY BITMAP FRAME]",
            escape,
            f"backend=kitty size={image.width}x{image.height}",
        ]
        return RenderOutput(
            backend=self.name,
            lines=lines,
            plan=render_plan,
            stats=(render_plan.stats if render_plan else None),
        )
