"""Unicode radar backend (mandatory baseline)."""

from __future__ import annotations

import math
from typing import Iterable

from .base import RadarBackend, RadarScene, RenderOutput
from .geometry import project_point


class UnicodeRadarBackend(RadarBackend):
    name = "unicode"

    def is_supported(self) -> bool:
        return True

    def render(self, scene: RadarScene, *, view: str, color: bool) -> RenderOutput:
        lines = self._render_grid(scene, view=view, width=41, height=13)
        return RenderOutput(backend=self.name, lines=lines)

    def _render_grid(self, scene: RadarScene, *, view: str, width: int, height: int) -> list[str]:
        width = max(21, width)
        height = max(9, height)
        grid = [[" " for _ in range(width)] for _ in range(height)]
        center_x = width // 2
        center_y = height // 2
        max_radius = max(1, min(center_x, center_y) - 1)

        for y in range(height):
            for x in range(width):
                dx = x - center_x
                dy = y - center_y
                radius = int(round(math.sqrt(dx * dx + dy * dy)))
                if radius == max_radius:
                    grid[y][x] = "·"
        grid[center_y][center_x] = "⊕"

        if not scene.ok:
            message = f"NO DATA: {scene.reason or 'NO_DATA'}"
            start_x = max(1, center_x - (len(message) // 2))
            for idx, ch in enumerate(message):
                x = start_x + idx
                if x < width - 1:
                    grid[center_y][x] = ch
            return ["".join(row) for row in grid]

        points = list(self._projected_points(scene.points, view=view))
        if not points:
            return ["".join(row) for row in grid]

        max_extent = max(1.0, max(max(abs(u), abs(v)) for u, v, _, _ in points))
        scale = float(max_radius) / max_extent

        for u, v, depth, vr_mps in points:
            x = int(round(center_x + u * scale))
            y = int(round(center_y - v * scale))
            x = min(width - 2, max(1, x))
            y = min(height - 2, max(1, y))
            marker = self._depth_marker(depth)
            grid[y][x] = marker
            arrow = "→" if vr_mps >= 0 else "←"
            if x + 1 < width - 1:
                grid[y][x + 1] = arrow

        return ["".join(row) for row in grid]

    @staticmethod
    def _projected_points(points: list, *, view: str) -> Iterable[tuple[float, float, float, float]]:
        for point in points:
            p = project_point(point, view)
            yield (p.u, p.v, p.depth, p.vr_mps)

    @staticmethod
    def _depth_marker(depth: float) -> str:
        if depth < -0.6:
            return "·"
        if depth < -0.1:
            return "◌"
        if depth < 0.4:
            return "◍"
        return "●"
