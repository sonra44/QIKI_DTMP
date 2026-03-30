import pytest

from qiki.services.operator_console.radar.projection import (
    iso_camera_basis,
    project_xyz_to_uv_m,
)


def test_iso_camera_basis_yaw_is_clockwise_from_plus_y() -> None:
    # yaw=0, pitch=0 -> forward along +Y, right along +X, up along +Z.
    basis = iso_camera_basis(yaw_deg=0.0, pitch_deg=0.0)
    rx, ry, rz = basis.right
    ux, uy, uz = basis.up

    assert rx == pytest.approx(1.0)
    assert ry == pytest.approx(0.0)
    assert rz == pytest.approx(0.0)

    assert ux == pytest.approx(0.0)
    assert uy == pytest.approx(0.0)
    assert uz == pytest.approx(1.0)


def test_projection_views_use_z_for_3d_views() -> None:
    x, y = 0.0, 100.0
    z0, z1 = 0.0, 50.0

    top0 = project_xyz_to_uv_m(x_m=x, y_m=y, z_m=z0, view="top")
    top1 = project_xyz_to_uv_m(x_m=x, y_m=y, z_m=z1, view="top")
    assert top0 == pytest.approx(top1)

    side0 = project_xyz_to_uv_m(x_m=x, y_m=y, z_m=z0, view="side")
    side1 = project_xyz_to_uv_m(x_m=x, y_m=y, z_m=z1, view="side")
    assert side0 != side1

    front0 = project_xyz_to_uv_m(x_m=x, y_m=y, z_m=z0, view="front")
    front1 = project_xyz_to_uv_m(x_m=x, y_m=y, z_m=z1, view="front")
    assert front0 != front1

    iso0 = project_xyz_to_uv_m(x_m=x, y_m=y, z_m=z0, view="iso", iso_yaw_deg=45.0, iso_pitch_deg=35.0)
    iso1 = project_xyz_to_uv_m(x_m=x, y_m=y, z_m=z1, view="iso", iso_yaw_deg=45.0, iso_pitch_deg=35.0)
    assert iso0 != iso1
