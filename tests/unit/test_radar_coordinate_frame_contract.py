import pytest

from qiki.shared.radar_coords import polar_to_xyz_m, xyz_to_bearing_deg
from qiki.services.faststream_bridge import radar_track_store
from qiki.services.operator_console.radar.unicode_ppi import BraillePpiRenderer


def test_radar_polar_contract_bearing_clockwise_from_plus_y() -> None:
    v0 = polar_to_xyz_m(range_m=10.0, bearing_deg=0.0, elev_deg=0.0)
    assert v0.x_m == pytest.approx(0.0)
    assert v0.y_m == pytest.approx(10.0)
    assert v0.z_m == pytest.approx(0.0)

    v90 = polar_to_xyz_m(range_m=10.0, bearing_deg=90.0, elev_deg=0.0)
    assert v90.x_m == pytest.approx(10.0)
    assert v90.y_m == pytest.approx(0.0)
    assert v90.z_m == pytest.approx(0.0)

    assert xyz_to_bearing_deg(x_m=0.0, y_m=10.0) == pytest.approx(0.0)
    assert xyz_to_bearing_deg(x_m=10.0, y_m=0.0) == pytest.approx(90.0)


def test_track_store_polar_cartesian_helpers_match_shared_contract() -> None:
    vec = radar_track_store._polar_to_cartesian(100.0, 30.0, 10.0)
    xyz = polar_to_xyz_m(range_m=100.0, bearing_deg=30.0, elev_deg=10.0)
    assert vec.x == pytest.approx(xyz.x_m)
    assert vec.y == pytest.approx(xyz.y_m)
    assert vec.z == pytest.approx(xyz.z_m)

    bearing = radar_track_store._cartesian_to_bearing(vec)
    assert bearing == pytest.approx(30.0)


def test_orion_unicode_ppi_polar_fallback_respects_elevation_in_side_view() -> None:
    renderer = BraillePpiRenderer(width_cells=20, height_cells=12, max_range_m=200.0)

    base = {"range_m": 100.0, "bearing_deg": 90.0}
    tracks_flat = [dict(base, elev_deg=0.0)]
    tracks_up = [dict(base, elev_deg=45.0)]

    out_flat = renderer.render_tracks(
        tracks_flat,
        view="side",
        zoom=1.0,
        pan_u_m=0.0,
        pan_v_m=0.0,
        draw_overlays=False,
        draw_vectors=False,
        draw_labels=False,
        rich=False,
    )
    out_up = renderer.render_tracks(
        tracks_up,
        view="side",
        zoom=1.0,
        pan_u_m=0.0,
        pan_v_m=0.0,
        draw_overlays=False,
        draw_vectors=False,
        draw_labels=False,
        rich=False,
    )

    assert isinstance(out_flat, str)
    assert isinstance(out_up, str)
    assert out_flat != out_up
