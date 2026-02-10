"""Unicode radar backend (mandatory baseline)."""

from __future__ import annotations

import math
from typing import Iterable

from .base import RadarBackend, RadarScene, RenderOutput
from .geometry import project_point
from qiki.services.q_core_agent.core.radar_view_state import RadarViewState

_ANSI_RESET = "\x1b[0m"
_ANSI_CYAN = "\x1b[36m"
_ANSI_YELLOW = "\x1b[33m"
_ANSI_RED = "\x1b[31m"
_ANSI_GREEN = "\x1b[32m"


class UnicodeRadarBackend(RadarBackend):
    name = "unicode"

    def is_supported(self) -> bool:
        return True

    def render(self, scene: RadarScene, *, view_state: RadarViewState, color: bool) -> RenderOutput:
        lines = self._render_grid(scene, view_state=view_state, color=color, width=41, height=13)
        return RenderOutput(backend=self.name, lines=lines)

    def _render_grid(
        self,
        scene: RadarScene,
        *,
        view_state: RadarViewState,
        color: bool,
        width: int,
        height: int,
    ) -> list[str]:
        width = max(21, width)
        height = max(9, height)
        grid = [[" " for _ in range(width)] for _ in range(height)]
        center_x = width // 2
        center_y = height // 2
        max_radius = max(1, min(center_x, center_y) - 1)

        if view_state.overlays_enabled:
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
            lines = ["".join(row) for row in grid]
            if color:
                return [self._colorize_line(line, scene.truth_state) for line in lines]
            return lines

        points = list(self._projected_points(scene.points, view_state=view_state))
        if not points:
            return ["".join(row) for row in grid]

        max_extent = max(1.0, max(max(abs(u), abs(v)) for _, u, v, _, _ in points))
        scale = (float(max_radius) / max_extent) * max(0.25, min(6.0, view_state.zoom))

        for point_id, u, v, depth, vr_mps in points:
            x = int(round(center_x + (u + view_state.pan_x) * scale))
            y = int(round(center_y - (v + view_state.pan_y) * scale))
            x = min(width - 2, max(1, x))
            y = min(height - 2, max(1, y))
            marker = self._depth_marker(depth)
            if view_state.selected_target_id and point_id == view_state.selected_target_id:
                marker = "◆"
            grid[y][x] = marker
            arrow = "→" if vr_mps >= 0 else "←"
            if x + 1 < width - 1:
                grid[y][x + 1] = arrow

        lines = ["".join(row) for row in grid]
        if color:
            return [self._colorize_line(line, scene.truth_state) for line in lines]
        return lines

    @staticmethod
    def _projected_points(points: list, *, view_state: RadarViewState) -> Iterable[tuple[str, float, float, float, float]]:
        for idx, point in enumerate(points):
            p = project_point(
                point,
                view_state.view,
                rot_yaw_deg=view_state.rot_yaw,
                rot_pitch_deg=view_state.rot_pitch,
            )
            point_id = str(point.metadata.get("target_id") or point.metadata.get("id") or f"target-{idx}")
            yield (point_id, p.u, p.v, p.depth, p.vr_mps)

    @staticmethod
    def _colorize_line(line: str, truth_state: str) -> str:
        state = (truth_state or "").upper()
        if state in {"NO_DATA", "STALE", "LOW_QUALITY"}:
            return f"{_ANSI_YELLOW}{line}{_ANSI_RESET}"
        if state in {"FALLBACK", "INVALID"}:
            return f"{_ANSI_RED}{line}{_ANSI_RESET}"
        if state == "OK":
            return f"{_ANSI_GREEN}{line}{_ANSI_RESET}"
        return f"{_ANSI_CYAN}{line}{_ANSI_RESET}"

    @staticmethod
    def _depth_marker(depth: float) -> str:
        if depth < -0.6:
            return "·"
        if depth < -0.1:
            return "◌"
        if depth < 0.4:
            return "◍"
        return "●"
