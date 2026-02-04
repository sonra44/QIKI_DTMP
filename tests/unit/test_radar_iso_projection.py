import pytest


def test_project_iso_moves_up_with_positive_z() -> None:
    from qiki.services.operator_console.radar.projection import project_xyz_to_uv_m

    u0, v0 = project_xyz_to_uv_m(x_m=0.0, y_m=0.0, z_m=0.0, view="iso", iso_yaw_deg=45.0, iso_pitch_deg=35.0)
    u1, v1 = project_xyz_to_uv_m(x_m=0.0, y_m=0.0, z_m=100.0, view="iso", iso_yaw_deg=45.0, iso_pitch_deg=35.0)

    assert u0 == pytest.approx(u1, abs=1e-6)
    assert v1 > v0


def test_project_iso_responds_to_x_and_y() -> None:
    from qiki.services.operator_console.radar.projection import project_xyz_to_uv_m

    u0, v0 = project_xyz_to_uv_m(x_m=0.0, y_m=0.0, z_m=0.0, view="iso", iso_yaw_deg=45.0, iso_pitch_deg=35.0)
    ux, vx = project_xyz_to_uv_m(x_m=100.0, y_m=0.0, z_m=0.0, view="iso", iso_yaw_deg=45.0, iso_pitch_deg=35.0)
    uy, vy = project_xyz_to_uv_m(x_m=0.0, y_m=100.0, z_m=0.0, view="iso", iso_yaw_deg=45.0, iso_pitch_deg=35.0)

    assert (ux, vx) != (u0, v0)
    assert (uy, vy) != (u0, v0)

