from __future__ import annotations

import math
from typing import NamedTuple


class RadarXYZ(NamedTuple):
    x_m: float
    y_m: float
    z_m: float


def polar_to_xyz_m(*, range_m: float, bearing_deg: float, elev_deg: float) -> RadarXYZ:
    """
    Convert radar polar coordinates to XYZ in meters using the Phase1 contract.

    World/navigation frame (right-handed):
    - +X: East / right (screen right in ORION Top view)
    - +Y: North / up (screen up in ORION Top view)
    - +Z: Up

    Angles:
    - bearing_deg: degrees clockwise from +Y (North). 0° is +Y, 90° is +X.
    - elev_deg: degrees up from the XY plane. 0° is in-plane, +90° is straight up.
    """

    r = max(float(range_m), 0.0)
    bearing_rad = math.radians(float(bearing_deg))
    elev_rad = math.radians(float(elev_deg))
    cos_elev = math.cos(elev_rad)

    x = r * cos_elev * math.sin(bearing_rad)
    y = r * cos_elev * math.cos(bearing_rad)
    z = r * math.sin(elev_rad)
    return RadarXYZ(x_m=float(x), y_m=float(y), z_m=float(z))


def xyz_to_bearing_deg(*, x_m: float, y_m: float) -> float:
    """Inverse of `polar_to_xyz_m` bearing convention (clockwise from +Y)."""

    # +Y -> 0°, +X -> 90°
    return float(math.degrees(math.atan2(float(x_m), float(y_m))) % 360.0)


def xyz_to_range_m(*, x_m: float, y_m: float, z_m: float) -> float:
    return float(math.sqrt(float(x_m) ** 2 + float(y_m) ** 2 + float(z_m) ** 2))


def xyz_to_elev_deg(*, x_m: float, y_m: float, z_m: float) -> float:
    horiz = float(math.sqrt(float(x_m) ** 2 + float(y_m) ** 2))
    return float(math.degrees(math.atan2(float(z_m), max(1e-9, horiz))))


def xyz_to_polar(
    *,
    x_m: float,
    y_m: float,
    z_m: float,
) -> tuple[float, float, float]:
    """
    Convert XYZ (meters) to polar (range_m, bearing_deg, elev_deg) using the Phase1 contract.
    """

    bearing_deg = xyz_to_bearing_deg(x_m=float(x_m), y_m=float(y_m))
    elev_deg = xyz_to_elev_deg(x_m=float(x_m), y_m=float(y_m), z_m=float(z_m))
    range_m = xyz_to_range_m(x_m=float(x_m), y_m=float(y_m), z_m=float(z_m))
    return (range_m, bearing_deg, elev_deg)
