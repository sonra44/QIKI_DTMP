"""Shared bitmap helpers for Kitty/SIXEL radar backends."""

from __future__ import annotations

from io import BytesIO

from .base import RadarScene
from .geometry import project_point
from qiki.services.q_core_agent.core.radar_view_state import RadarViewState


def scene_to_image(
    scene: RadarScene,
    *,
    view_state: RadarViewState,
    width: int = 240,
    height: int = 120,
    color: bool = True,
):
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Pillow is required for bitmap radar backends") from exc

    bg = (10, 12, 16, 255)
    fg = (190, 210, 230, 255)
    accent = (120, 230, 190, 255) if color else fg
    warn = (235, 120, 120, 255) if color else fg

    image = Image.new("RGBA", (width, height), color=bg)
    draw = ImageDraw.Draw(image)
    cx, cy = width // 2, height // 2
    radius = min(cx, cy) - 8
    if view_state.overlays_enabled:
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=fg, width=1)
        draw.line((cx, cy - radius, cx, cy + radius), fill=(80, 90, 110, 255), width=1)
        draw.line((cx - radius, cy, cx + radius, cy), fill=(80, 90, 110, 255), width=1)

    if not scene.ok:
        draw.text((12, cy - 6), f"NO DATA: {scene.reason or 'NO_DATA'}", fill=warn)
        return image

    if not scene.points:
        return image

    projected = [
        (
            str(p.metadata.get("target_id") or p.metadata.get("id") or f"target-{idx}"),
            project_point(
                p,
                view_state.view,
                rot_yaw_deg=view_state.rot_yaw,
                rot_pitch_deg=view_state.rot_pitch,
            ),
        )
        for idx, p in enumerate(scene.points)
    ]
    max_extent = max(1.0, max(max(abs(p.u), abs(p.v)) for _, p in projected))
    scale = (float(radius - 4) / max_extent) * max(0.25, min(6.0, view_state.zoom))

    for point_id, p in projected:
        x = int(round(cx + (p.u + view_state.pan_x) * scale))
        y = int(round(cy - (p.v + view_state.pan_y) * scale))
        depth = max(-1.0, min(1.0, p.depth / 30.0))
        size = 2 if depth < -0.3 else 3 if depth < 0.4 else 4
        col = accent if p.vr_mps >= 0 else warn
        if view_state.selected_target_id and view_state.selected_target_id == point_id:
            col = (255, 230, 80, 255) if color else fg
            size += 1
        draw.ellipse((x - size, y - size, x + size, y + size), fill=col)
        tail = 6 if p.vr_mps >= 0 else -6
        draw.line((x, y, x + tail, y), fill=col, width=1)

    return image


def image_to_png_bytes(image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def image_to_sixel_text(image) -> str:
    buf = BytesIO()
    try:
        image.save(buf, format="SIXEL")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("SIXEL encoder is unavailable in current Pillow build") from exc
    data = buf.getvalue()
    return data.decode("latin1", errors="ignore")
