from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CameraBasis:
    right: tuple[float, float, float]
    up: tuple[float, float, float]


def _norm(v: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = v
    m = math.sqrt(x * x + y * y + z * z)
    if m <= 0:
        return (0.0, 0.0, 0.0)
    return (x / m, y / m, z / m)


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    ax, ay, az = a
    bx, by, bz = b
    return (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def iso_camera_basis(*, yaw_deg: float, pitch_deg: float) -> CameraBasis:
    """Return a stable camera basis for ISO (pseudo-3D) projection.

    Coordinate canon (see bot_source_of_truth.md): X forward, Y left, Z up.

    The camera is defined by yaw around +Z and pitch above the horizon.
    We build an orthonormal basis (right, up) from a forward vector and the world up.
    """

    yaw = math.radians(float(yaw_deg))
    pitch = math.radians(float(pitch_deg))

    # Forward unit vector in world coordinates.
    forward = (
        math.cos(pitch) * math.cos(yaw),
        math.cos(pitch) * math.sin(yaw),
        math.sin(pitch),
    )
    up_world = (0.0, 0.0, 1.0)
    right = _norm(_cross(forward, up_world))
    up = _norm(_cross(right, forward))
    return CameraBasis(right=right, up=up)


def project_xyz_to_uv_m(
    *,
    x_m: float,
    y_m: float,
    z_m: float,
    view: str,
    iso_yaw_deg: float = 45.0,
    iso_pitch_deg: float = 35.0,
) -> tuple[float, float]:
    view_norm = (view or "").strip().lower()
    if view_norm == "top":
        return (float(x_m), float(y_m))
    if view_norm == "side":
        return (float(x_m), float(z_m))
    if view_norm == "front":
        return (float(y_m), float(z_m))
    if view_norm == "iso":
        basis = iso_camera_basis(yaw_deg=iso_yaw_deg, pitch_deg=iso_pitch_deg)
        p = (float(x_m), float(y_m), float(z_m))
        return (_dot(p, basis.right), _dot(p, basis.up))
    return (float(x_m), float(y_m))

