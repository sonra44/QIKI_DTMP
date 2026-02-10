"""Shared bitmap helpers for Kitty/SIXEL radar backends."""

from __future__ import annotations

from io import BytesIO

from .base import RadarScene
from .geometry import project_point
from qiki.services.q_core_agent.core.radar_render_policy import RadarRenderPlan
from qiki.services.q_core_agent.core.radar_view_state import RadarViewState


def scene_to_image(
    scene: RadarScene,
    *,
    view_state: RadarViewState,
    width: int = 240,
    height: int = 120,
    color: bool = True,
    render_plan: RadarRenderPlan | None = None,
):
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Pillow is required for bitmap radar backends") from exc

    bg = (10, 12, 16, 255)
    fg = (190, 210, 230, 255)
    accent = (120, 230, 190, 255) if color else fg
    warn = (235, 120, 120, 255) if color else fg

    bitmap_scale = render_plan.bitmap_scale if render_plan is not None else 1.0
    width = max(80, int(width * bitmap_scale))
    height = max(40, int(height * bitmap_scale))
    image = Image.new("RGBA", (width, height), color=bg)
    draw = ImageDraw.Draw(image)
    cx, cy = width // 2, height // 2
    radius = min(cx, cy) - 8
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
    if draw_rings:
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=fg, width=1)
    if draw_grid:
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

    if draw_trails:
        for trail in scene.trails.values():
            for trail_point in trail:
                p = project_point(
                    trail_point,
                    view_state.view,
                    rot_yaw_deg=view_state.rot_yaw,
                    rot_pitch_deg=view_state.rot_pitch,
                )
                tx = int(round(cx + (p.u + view_state.pan_x) * scale))
                ty = int(round(cy - (p.v + view_state.pan_y) * scale))
                draw.ellipse((tx - 1, ty - 1, tx + 1, ty + 1), fill=(100, 110, 130, 255))

    for point_id, p in projected:
        x = int(round(cx + (p.u + view_state.pan_x) * scale))
        y = int(round(cy - (p.v + view_state.pan_y) * scale))
        depth = max(-1.0, min(1.0, p.depth / 30.0))
        size = 2 if depth < -0.3 else 3 if depth < 0.4 else 4
        col = accent if p.vr_mps >= 0 else warn
        if view_state.selected_target_id and view_state.selected_target_id == point_id and (
            render_plan is None or render_plan.draw_selection_highlight
        ):
            col = (255, 230, 80, 255) if color else fg
            size += 1
        draw.ellipse((x - size, y - size, x + size, y + size), fill=col)
        if draw_vectors:
            tail = 6 if p.vr_mps >= 0 else -6
            draw.line((x, y, x + tail, y), fill=col, width=1)
        if draw_labels:
            draw.text((x + 3, y - 3), point_id[:6], fill=fg)

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
