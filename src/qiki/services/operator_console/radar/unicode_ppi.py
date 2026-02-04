from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from rich.style import Style
from rich.text import Text

from qiki.services.operator_console.radar.projection import project_xyz_to_uv_m


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

    @staticmethod
    def _iff_kind(payload: dict[str, Any]) -> str | None:
        raw = payload.get("iff", payload.get("iff_class", payload.get("iffClass")))
        if isinstance(raw, str):
            s = raw.strip()
            if s.isdigit():
                try:
                    raw = int(s)
                except Exception:
                    raw = s
            else:
                raw = s.upper()
        if isinstance(raw, int):
            # qiki.shared.models.radar.FriendFoeEnum (aligned with proto):
            # 0 UNSPECIFIED, 1 FRIEND, 2 FOE, 3 UNKNOWN
            return {1: "friend", 2: "foe", 3: "unknown"}.get(raw)
        if isinstance(raw, str) and raw:
            if "FRIEND" in raw:
                return "friend"
            if "FOE" in raw:
                return "foe"
            if "UNKNOWN" in raw:
                return "unknown"
        return None

    @classmethod
    def _track_style(cls, payload: dict[str, Any]) -> Style:
        kind = cls._iff_kind(payload)
        if kind == "friend":
            return Style(color="#00ff66")
        if kind == "foe":
            return Style(color="#ff3355", bold=True)
        if kind == "unknown":
            return Style(color="#ffb000", bold=True)
        return Style(color="#00b7ff")

    @staticmethod
    def _velocity_xyz_mps(payload: dict[str, Any]) -> tuple[float, float, float] | None:
        vel = payload.get("velocity")
        if isinstance(vel, dict):
            try:
                return (float(vel.get("x")), float(vel.get("y")), float(vel.get("z")))
            except Exception:
                pass
        for keys in (
            ("vx_mps", "vy_mps", "vz_mps"),
            ("vx", "vy", "vz"),
            ("vel_x_mps", "vel_y_mps", "vel_z_mps"),
        ):
            try:
                vx = payload.get(keys[0])
                vy = payload.get(keys[1])
                vz = payload.get(keys[2])
                if vx is None or vy is None:
                    continue
                return (float(vx), float(vy), float(vz or 0.0))
            except Exception:
                continue
        return None

    def render_tracks(
        self,
        tracks: list[dict[str, Any]] | list[tuple[str, dict[str, Any]]],
        *,
        view: str = "top",
        zoom: float = 1.0,
        pan_u_m: float = 0.0,
        pan_v_m: float = 0.0,
        draw_overlays: bool = True,
        draw_vectors: bool = False,
        draw_labels: bool = False,
        rich: bool = False,
        selected_track_id: str | None = None,
        iso_yaw_deg: float = 45.0,
        iso_pitch_deg: float = 35.0,
    ) -> str | Text:
        width_cells = max(10, int(self.width_cells))
        height_cells = max(6, int(self.height_cells))
        max_range_m = max(1.0, float(self.max_range_m))
        view_norm = (view or "").strip().lower()
        if view_norm not in {"top", "side", "front", "iso"}:
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
        cell_styles: list[list[Style | None]] = [[None for _ in range(width_cells)] for _ in range(height_cells)]
        cell_priorities: list[list[int]] = [[-1 for _ in range(width_cells)] for _ in range(height_cells)]
        cell_overrides: list[list[str | None]] = [[None for _ in range(width_cells)] for _ in range(height_cells)]

        selected_id = str(selected_track_id) if selected_track_id is not None else None
        overlay_style = Style(color="#20663a", dim=True)
        selected_style = Style(color="#ffffff", bold=True)
        vector_style = Style(color="#a0a0a0", dim=True)

        def plot_px(px: int, py: int, *, style: Style | None = None, priority: int = 0) -> None:
            if px < 0 or py < 0 or px >= width_px or py >= height_px:
                return
            cell_x = px // 2
            cell_y = py // 4
            local_x = px % 2
            local_y = py % 4
            cell_bits[cell_y][cell_x] |= _dot_bit(local_x, local_y)
            if style is not None and priority >= cell_priorities[cell_y][cell_x]:
                cell_priorities[cell_y][cell_x] = int(priority)
                cell_styles[cell_y][cell_x] = style

        def override_cell(cell_x: int, cell_y: int, ch: str, *, style: Style | None = None, priority: int = 0) -> None:
            if cell_x < 0 or cell_y < 0 or cell_x >= width_cells or cell_y >= height_cells:
                return
            if priority >= cell_priorities[cell_y][cell_x]:
                cell_priorities[cell_y][cell_x] = int(priority)
                cell_overrides[cell_y][cell_x] = (ch or " ")[:1]
                if style is not None:
                    cell_styles[cell_y][cell_x] = style

        if draw_overlays:
            # Baseline overlays (always visible; no-mocks).
            # - Center mark
            # - Range rings (25/50/75/100%)
            plot_px(center_px_x, center_px_y, style=overlay_style, priority=10)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                plot_px(center_px_x + dx, center_px_y + dy, style=overlay_style, priority=10)

            ring_radii = [0.25, 0.5, 0.75, 1.0]
            base_radius_px = max(2.0, min(width_px, height_px) / 2 - 1.0)
            steps = max(36, int(base_radius_px * 3))
            for ratio in ring_radii:
                radius = base_radius_px * ratio
                for i in range(steps):
                    ang = 2 * math.pi * i / steps
                    x = int(round(center_px_x + radius * math.sin(ang)))
                    y = int(round(center_px_y - radius * math.cos(ang)))
                    plot_px(x, y, style=overlay_style, priority=10)

        labels_enabled = bool(draw_labels) and float(zoom_f) >= 2.0
        vectors_enabled = bool(draw_vectors)
        vector_seconds = 8.0

        for item in tracks:
            track_id: str | None = None
            payload: dict[str, Any] | None = None
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], dict):
                track_id = item[0]
                payload = item[1]
            elif isinstance(item, dict):
                payload = item
            if payload is None:
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
                    x_m = None
                    y_m = None
                    z_m = None

            if x_m is None or y_m is None:
                r = payload.get("range_m")
                b = payload.get("bearing_deg")
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

            u_m, v_m = project_xyz_to_uv_m(
                x_m=float(x_m),
                y_m=float(y_m),
                z_m=float(z_m),
                view=view_norm,
                iso_yaw_deg=float(iso_yaw_deg),
                iso_pitch_deg=float(iso_pitch_deg),
            )

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
            if selected_id is not None and track_id is not None and str(track_id) == selected_id:
                style = selected_style
                priority = 100
            else:
                style = self._track_style(payload)
                priority = 50
            plot_px(px, py, style=style, priority=priority)

            if vectors_enabled:
                vel = self._velocity_xyz_mps(payload)
                if vel is not None:
                    vx, vy, vz = vel
                    du_mps, dv_mps = project_xyz_to_uv_m(
                        x_m=float(vx),
                        y_m=float(vy),
                        z_m=float(vz),
                        view=view_norm,
                        iso_yaw_deg=float(iso_yaw_deg),
                        iso_pitch_deg=float(iso_pitch_deg),
                    )
                    u2_m = float(u_m) + float(du_mps) * float(vector_seconds)
                    v2_m = float(v_m) + float(dv_mps) * float(vector_seconds)
                    nx2 = max(-1.0, min(1.0, u2_m / effective_range_m))
                    ny2 = max(-1.0, min(1.0, v2_m / effective_range_m))
                    px2 = int(round(center_px_x + nx2 * (width_px / 2 - 1)))
                    py2 = int(round(center_px_y - ny2 * (height_px / 2 - 1)))
                    dx = px2 - px
                    dy = py2 - py
                    steps = max(0, min(250, int(max(abs(dx), abs(dy)))))
                    if steps >= 2:
                        for i in range(1, steps + 1):
                            x = int(round(px + dx * i / steps))
                            y = int(round(py + dy * i / steps))
                            plot_px(x, y, style=vector_style, priority=20)

            if labels_enabled and track_id is not None:
                label = str(track_id).strip()
                if label:
                    label = label[-4:]
                    cell_x = px // 2
                    cell_y = py // 4
                    start_x = cell_x + 1
                    for i, ch in enumerate(label):
                        override_cell(start_x + i, cell_y, ch, style=style, priority=priority)

        # Render to lines.
        lines: list[str] = []
        for y, row in enumerate(cell_bits):
            chars: list[str] = []
            for x, bits in enumerate(row):
                override = cell_overrides[y][x]
                if override is not None:
                    chars.append(override)
                else:
                    chars.append(chr(0x2800 + bits) if bits else " ")
            lines.append("".join(chars))
        out = "\n".join(lines)
        if not rich:
            return out

        text = Text(out)
        stride = width_cells + 1
        for y in range(height_cells):
            base = y * stride
            for x in range(width_cells):
                style = cell_styles[y][x]
                if style is None:
                    continue
                ch = lines[y][x]
                if ch == " ":
                    continue
                i = base + x
                text.stylize(style, i, i + 1)
        return text


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
    iso_yaw_deg: float = 45.0,
    iso_pitch_deg: float = 35.0,
) -> str | None:
    """Pick nearest track by click position in the PPI widget cell space.

    This is a pure helper for ORION mouse selection (no terminal I/O).
    """

    width_cells = max(10, int(width_cells))
    height_cells = max(6, int(height_cells))
    max_range_m = max(1.0, float(max_range_m))
    view_norm = (view or "").strip().lower()
    if view_norm not in {"top", "side", "front", "iso"}:
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

        u_m, v_m = project_xyz_to_uv_m(
            x_m=float(x_m),
            y_m=float(y_m),
            z_m=float(z_m),
            view=view_norm,
            iso_yaw_deg=float(iso_yaw_deg),
            iso_pitch_deg=float(iso_pitch_deg),
        )

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
