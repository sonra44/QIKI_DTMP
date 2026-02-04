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

    def render_tracks(self, tracks: list[dict[str, Any]]) -> str:
        width_cells = max(10, int(self.width_cells))
        height_cells = max(6, int(self.height_cells))
        max_range_m = max(1.0, float(self.max_range_m))

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

        for t in tracks:
            if not isinstance(t, dict):
                continue

            x_m: float | None = None
            y_m: float | None = None

            pos = t.get("position")
            if isinstance(pos, dict):
                try:
                    x_m = float(pos.get("x"))
                    y_m = float(pos.get("y"))
                except Exception:
                    x_m = None
                    y_m = None

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

            # Map meters to pixels (square viewport, clamped).
            nx = max(-1.0, min(1.0, float(x_m) / max_range_m))
            ny = max(-1.0, min(1.0, float(y_m) / max_range_m))

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

