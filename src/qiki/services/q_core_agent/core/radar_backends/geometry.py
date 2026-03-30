"""Projection helpers for radar rendering backends."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .base import RadarPoint


@dataclass(frozen=True)
class ProjectedPoint:
    u: float
    v: float
    depth: float
    vr_mps: float


def project_point(
    point: RadarPoint,
    view: str,
    *,
    rot_yaw_deg: float = 0.0,
    rot_pitch_deg: float = 0.0,
) -> ProjectedPoint:
    x = float(point.x)
    y = float(point.y)
    z = float(point.z)
    if view == "top":
        return ProjectedPoint(u=x, v=y, depth=z, vr_mps=point.vr_mps)
    if view == "side":
        return ProjectedPoint(u=x, v=z, depth=y, vr_mps=point.vr_mps)
    if view == "front":
        return ProjectedPoint(u=y, v=z, depth=x, vr_mps=point.vr_mps)
    if view == "iso":
        yaw = math.radians(rot_yaw_deg)
        pitch = math.radians(rot_pitch_deg)
        xr = (x * math.cos(yaw)) - (y * math.sin(yaw))
        yr = (x * math.sin(yaw)) + (y * math.cos(yaw))
        zr = z
        yp = (yr * math.cos(pitch)) - (zr * math.sin(pitch))
        zp = (yr * math.sin(pitch)) + (zr * math.cos(pitch))
        u = (xr - yp) * math.sqrt(0.5)
        v = ((xr + yp) * 0.35) - zp * 0.75
        return ProjectedPoint(u=u, v=v, depth=zp, vr_mps=point.vr_mps)
    return ProjectedPoint(u=x, v=y, depth=z, vr_mps=point.vr_mps)
