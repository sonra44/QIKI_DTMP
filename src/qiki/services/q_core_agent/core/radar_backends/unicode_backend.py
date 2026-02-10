"""Unicode radar backend (mandatory baseline)."""

from __future__ import annotations

import math
from typing import Iterable

from .base import RadarBackend, RadarScene, RenderOutput
from .geometry import project_point
from qiki.services.q_core_agent.core.radar_render_policy import RadarRenderPlan
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

    def render(
        self,
        scene: RadarScene,
        *,
        view_state: RadarViewState,
        color: bool,
        render_plan: RadarRenderPlan | None = None,
    ) -> RenderOutput:
        lines = self._render_grid(scene, view_state=view_state, color=color, width=41, height=13, render_plan=render_plan)
        return RenderOutput(backend=self.name, lines=lines, plan=render_plan, stats=(render_plan.stats if render_plan else None))

    def _render_grid(
        self,
        scene: RadarScene,
        *,
        view_state: RadarViewState,
        color: bool,
        width: int,
        height: int,
        render_plan: RadarRenderPlan | None,
    ) -> list[str]:
        width = max(21, width)
        height = max(9, height)
        grid = [[" " for _ in range(width)] for _ in range(height)]
        center_x = width // 2
        center_y = height // 2
        max_radius = max(1, min(center_x, center_y) - 1)

        draw_grid = view_state.overlays_enabled
        draw_rings = view_state.overlays_enabled
        draw_vectors = view_state.overlays_enabled
        draw_labels = False
        draw_trails = view_state.overlays_enabled
        if render_plan is not None:
            draw_grid = render_plan.draw_grid
            draw_rings = render_plan.draw_range_rings
            draw_vectors = render_plan.draw_vectors
            draw_labels = render_plan.draw_labels
            draw_trails = render_plan.draw_trails
        if draw_grid:
            for y in range(height):
                grid[y][center_x] = "│"
            for x in range(width):
                grid[center_y][x] = "─"
        if draw_rings:
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

        if draw_trails:
            for point_id, trail in scene.trails.items():
                for trail_point in trail:
                    p = project_point(
                        trail_point,
                        view_state.view,
                        rot_yaw_deg=view_state.rot_yaw,
                        rot_pitch_deg=view_state.rot_pitch,
                    )
                    tx = int(round(center_x + (p.u + view_state.pan_x) * scale))
                    ty = int(round(center_y - (p.v + view_state.pan_y) * scale))
                    tx = min(width - 2, max(1, tx))
                    ty = min(height - 2, max(1, ty))
                    if grid[ty][tx] == " ":
                        grid[ty][tx] = "·"

        for point_id, u, v, depth, vr_mps in points:
            x = int(round(center_x + (u + view_state.pan_x) * scale))
            y = int(round(center_y - (v + view_state.pan_y) * scale))
            x = min(width - 2, max(1, x))
            y = min(height - 2, max(1, y))
            marker = self._depth_marker(depth)
            if view_state.selected_target_id and point_id == view_state.selected_target_id and (
                render_plan is None or render_plan.draw_selection_highlight
            ):
                marker = "◆"
            grid[y][x] = marker
            if draw_vectors:
                arrow = "→" if vr_mps >= 0 else "←"
                if x + 1 < width - 1:
                    grid[y][x + 1] = arrow
            if draw_labels:
                label = point_id[:4]
                start = min(width - len(label) - 1, x + 1)
                if start > 0:
                    for idx, ch in enumerate(label):
                        grid[y][start + idx] = ch

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
