from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


def _dot_bit(local_x: int, local_y: int) -> int:
    """Return braille dot bit for a pixel in a 2x4 cell.

    Braille dot layout (2 columns x 4 rows):
      y=0: dot1 (left),  dot4 (right)
      y=1: dot2 (left),  dot5 (right)
      y=2: dot3 (left),  dot6 (right)
      y=3: dot7 (left),  dot8 (right)
    """

    if local_y == 0:
        return 1 if local_x == 0 else 8
    if local_y == 1:
        return 2 if local_x == 0 else 16
    if local_y == 2:
        return 4 if local_x == 0 else 32
    return 64 if local_x == 0 else 128


@dataclass(slots=True)
class BraillePpiRenderer:
    """Unicode high-density radar PPI renderer (no external deps).

    Input tracks are dict payloads (as stored in ORION's `_tracks_by_id`).
    Primary signal is `position.{x,y,z}` (3D truth). Fallback is polar `range_m` + `bearing_deg`.
    """

    width_cells: int
    height_cells: int
    max_range_m: float

    def render_tracks(
        self,
        tracks: list[dict[str, Any]],
        *,
        view: str = "top",
        zoom: float = 1.0,
        pan_u_m: float = 0.0,
        pan_v_m: float = 0.0,
        draw_overlays: bool = True,
    ) -> str:
        width_cells = max(10, int(self.width_cells))
        height_cells = max(6, int(self.height_cells))
        max_range_m = max(1.0, float(self.max_range_m))
        view_norm = (view or "").strip().lower()
        if view_norm not in {"top", "side", "front"}:
            view_norm = "top"
        try:
            zoom_f = float(zoom)
        except Exception:
            zoom_f = 1.0
        zoom_f = max(0.1, min(100.0, zoom_f))
        effective_range_m = max(1.0, max_range_m / zoom_f)

        # Braille “pixel” grid resolution per terminal cell.
        width_px = width_cells * 2
        height_px = height_cells * 4

        center_px_x = width_px // 2
        center_px_y = height_px // 2

        # Accumulate braille bitmasks per cell.
        cell_bits: list[list[int]] = [[0 for _ in range(width_cells)] for _ in range(height_cells)]

        def plot_px(px: int, py: int) -> None:
            if px < 0 or py < 0 or px >= width_px or py >= height_px:
                return
            cell_x = px // 2
            cell_y = py // 4
            local_x = px % 2
            local_y = py % 4
            cell_bits[cell_y][cell_x] |= _dot_bit(local_x, local_y)

        if draw_overlays:
            # Baseline overlays (always visible; no-mocks).
            # - Center mark
            # - Range rings (25/50/75/100%)
            plot_px(center_px_x, center_px_y)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                plot_px(center_px_x + dx, center_px_y + dy)

            ring_radii = [0.25, 0.5, 0.75, 1.0]
            base_radius_px = max(2.0, min(width_px, height_px) / 2 - 1.0)
            steps = max(36, int(base_radius_px * 3))
            for ratio in ring_radii:
                radius = base_radius_px * ratio
                for i in range(steps):
                    ang = 2 * math.pi * i / steps
                    x = int(round(center_px_x + radius * math.sin(ang)))
                    y = int(round(center_px_y - radius * math.cos(ang)))
                    plot_px(x, y)

        for t in tracks:
            if not isinstance(t, dict):
                continue

            x_m: float | None = None
            y_m: float | None = None
            z_m: float | None = None

            pos = t.get("position")
            if isinstance(pos, dict):
                try:
                    x_m = float(pos.get("x"))
                    y_m = float(pos.get("y"))
                    z_m = float(pos.get("z"))
                except Exception:
                    x_m = None
                    y_m = None
                    z_m = None

            if x_m is None or y_m is None:
                r = t.get("range_m")
                b = t.get("bearing_deg")
                try:
                    r_f = float(r)
                    b_f = float(b)
                except Exception:
                    continue
                # Bearing is degrees clockwise from +Y (north) in existing UI.
                bearing_rad = math.radians(b_f)
                x_m = r_f * math.sin(bearing_rad)
                y_m = r_f * math.cos(bearing_rad)
                z_m = 0.0

            if z_m is None:
                z_m = 0.0

            if view_norm == "top":
                u_m, v_m = float(x_m), float(y_m)
            elif view_norm == "side":
                u_m, v_m = float(x_m), float(z_m)
            else:
                u_m, v_m = float(y_m), float(z_m)

            # Pan is in meters in the selected view plane.
            try:
                u_m -= float(pan_u_m)
                v_m -= float(pan_v_m)
            except Exception:
                pass

            # Map meters to pixels (square viewport, clamped).
            nx = max(-1.0, min(1.0, u_m / effective_range_m))
            ny = max(-1.0, min(1.0, v_m / effective_range_m))

            px = int(round(center_px_x + nx * (width_px / 2 - 1)))
            py = int(round(center_px_y - ny * (height_px / 2 - 1)))
            plot_px(px, py)

        # Render to lines.
        lines: list[str] = []
        for row in cell_bits:
            chars = []
            for bits in row:
                chars.append(chr(0x2800 + bits) if bits else " ")
            lines.append("".join(chars))
        return "\n".join(lines)


def pick_nearest_track_id(
    tracks: list[tuple[str, dict[str, Any]]],
    *,
    click_cell_x: int,
    click_cell_y: int,
    width_cells: int,
    height_cells: int,
    max_range_m: float,
    view: str = "top",
    zoom: float = 1.0,
    pan_u_m: float = 0.0,
    pan_v_m: float = 0.0,
    pick_radius_cells: float = 2.5,
) -> str | None:
    """Pick nearest track by click position in the PPI widget cell space.

    This is a pure helper for ORION mouse selection (no terminal I/O).
    """

    width_cells = max(10, int(width_cells))
    height_cells = max(6, int(height_cells))
    max_range_m = max(1.0, float(max_range_m))
    view_norm = (view or "").strip().lower()
    if view_norm not in {"top", "side", "front"}:
        view_norm = "top"
    try:
        zoom_f = float(zoom)
    except Exception:
        zoom_f = 1.0
    zoom_f = max(0.1, min(100.0, zoom_f))
    effective_range_m = max(1.0, max_range_m / zoom_f)

    width_px = width_cells * 2
    height_px = height_cells * 4
    center_px_x = width_px // 2
    center_px_y = height_px // 2

    # Click in cell coords -> approximate pixel coords (center of the cell).
    click_px_x = int(click_cell_x) * 2 + 1
    click_px_y = int(click_cell_y) * 4 + 2

    # Radius threshold in pixels (heuristic; good enough for TUI selection).
    pick_radius_px = max(2.0, float(pick_radius_cells) * 3.0)
    pick_radius_sq = pick_radius_px * pick_radius_px

    best_id: str | None = None
    best_dist_sq: float | None = None

    for track_id, payload in tracks:
        if not isinstance(payload, dict):
            continue

        x_m: float | None = None
        y_m: float | None = None
        z_m: float | None = None

        pos = payload.get("position")
        if isinstance(pos, dict):
            try:
                x_m = float(pos.get("x"))
                y_m = float(pos.get("y"))
                z_m = float(pos.get("z"))
            except Exception:
                x_m = y_m = z_m = None

        if x_m is None or y_m is None:
            r = payload.get("range_m")
            b = payload.get("bearing_deg")
            try:
                r_f = float(r)
                b_f = float(b)
            except Exception:
                continue
            bearing_rad = math.radians(b_f)
            x_m = r_f * math.sin(bearing_rad)
            y_m = r_f * math.cos(bearing_rad)
            z_m = 0.0

        if z_m is None:
            z_m = 0.0

        if view_norm == "top":
            u_m, v_m = float(x_m), float(y_m)
        elif view_norm == "side":
            u_m, v_m = float(x_m), float(z_m)
        else:
            u_m, v_m = float(y_m), float(z_m)

        try:
            u_m -= float(pan_u_m)
            v_m -= float(pan_v_m)
        except Exception:
            pass

        nx = max(-1.0, min(1.0, u_m / effective_range_m))
        ny = max(-1.0, min(1.0, v_m / effective_range_m))
        px = int(round(center_px_x + nx * (width_px / 2 - 1)))
        py = int(round(center_px_y - ny * (height_px / 2 - 1)))

        dx = float(click_px_x - px)
        dy = float(click_px_y - py)
        dist_sq = dx * dx + dy * dy
        if dist_sq > pick_radius_sq:
            continue
        if best_dist_sq is None or dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best_id = str(track_id)

    return best_id
