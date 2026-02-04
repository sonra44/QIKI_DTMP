from __future__ import annotations

import math
from typing import Any

from qiki.services.operator_console.radar.projection import project_xyz_to_uv_m


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


def _track_rgba(payload: dict[str, Any]) -> tuple[int, int, int, int]:
    kind = _iff_kind(payload)
    if kind == "friend":
        return (0, 255, 102, 255)
    if kind == "foe":
        return (255, 51, 85, 255)
    if kind == "unknown":
        return (255, 176, 0, 255)
    return (0, 183, 255, 255)


def render_bitmap_ppi(
    tracks: list[tuple[str, dict[str, Any]]],
    *,
    width_px: int,
    height_px: int,
    max_range_m: float,
    view: str = "top",
    zoom: float = 1.0,
    pan_u_m: float = 0.0,
    pan_v_m: float = 0.0,
    iso_yaw_deg: float = 45.0,
    iso_pitch_deg: float = 35.0,
    selected_track_id: str | None = None,
    draw_overlays: bool = True,
):
    """Render radar PPI to a PIL Image (RGBA).

    Lazy-imports Pillow to keep qiki-dev unit tests independent of PIL.
    """

    from PIL import Image, ImageDraw  # type: ignore[import-not-found]

    width_px = max(64, int(width_px))
    height_px = max(48, int(height_px))
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

    img = Image.new("RGBA", (width_px, height_px), (5, 5, 5, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    cx = width_px // 2
    cy = height_px // 2

    if draw_overlays:
        overlay = (32, 102, 58, 140)
        # Center cross.
        draw.line((cx - 6, cy, cx + 6, cy), fill=overlay, width=1)
        draw.line((cx, cy - 6, cx, cy + 6), fill=overlay, width=1)
        # Range rings.
        base_r = max(6, min(width_px, height_px) // 2 - 4)
        for ratio in (0.25, 0.5, 0.75, 1.0):
            r = int(round(base_r * ratio))
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=overlay, width=1)

    sel = str(selected_track_id) if selected_track_id is not None else None

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

        px = int(round(cx + nx * (width_px / 2 - 2)))
        py = int(round(cy - ny * (height_px / 2 - 2)))

        if sel is not None and str(track_id) == sel:
            color = (255, 255, 255, 255)
            r0 = 4
        else:
            color = _track_rgba(payload)
            r0 = 2
        draw.ellipse((px - r0, py - r0, px + r0, py + r0), fill=color, outline=None)

    return img
