"""SIXEL backend for radar pipeline."""

from __future__ import annotations

import os

from .base import RadarBackend, RadarScene, RenderOutput
from .bitmap_common import image_to_sixel_text, scene_to_image


class SixelRadarBackend(RadarBackend):
    name = "sixel"

    def is_supported(self) -> bool:
        if os.getenv("QIKI_FORCE_SIXEL_SUPPORTED", "").strip() == "1":
            return True
        term = os.getenv("TERM", "").lower()
        return "sixel" in term

    def render(self, scene: RadarScene, *, view: str, color: bool) -> RenderOutput:
        if not self.is_supported():
            raise RuntimeError("SIXEL backend is unsupported in this terminal")
        image = scene_to_image(scene, view=view, color=color)
        sixel = image_to_sixel_text(image)
        lines = [
            "[SIXEL BITMAP FRAME]",
            sixel,
            f"backend=sixel size={image.width}x{image.height}",
        ]
        return RenderOutput(backend=self.name, lines=lines)
