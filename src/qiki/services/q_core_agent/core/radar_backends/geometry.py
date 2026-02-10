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


def project_point(point: RadarPoint, view: str) -> ProjectedPoint:
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
        # Clockwise rotation around +Y-like up-axis with simple pseudo-3D scaling.
        u = (x - y) * math.sqrt(0.5)
        v = ((x + y) * 0.35) - z * 0.75
        return ProjectedPoint(u=u, v=v, depth=z, vr_mps=point.vr_mps)
    return ProjectedPoint(u=x, v=y, depth=z, vr_mps=point.vr_mps)
