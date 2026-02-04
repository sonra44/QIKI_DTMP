from qiki.services.operator_console.radar.unicode_ppi import BraillePpiRenderer


def test_braille_ppi_empty_has_stable_dimensions() -> None:
    r = BraillePpiRenderer(width_cells=12, height_cells=7, max_range_m=500.0)
    out = r.render_tracks([])
    lines = out.splitlines()
    assert len(lines) == 7
    assert all(len(line) == 12 for line in lines)


def test_braille_ppi_plots_center_point() -> None:
    r = BraillePpiRenderer(width_cells=12, height_cells=7, max_range_m=500.0)
    out = r.render_tracks([{"position": {"x": 0.0, "y": 0.0, "z": 0.0}}])
    assert any(ch != " " for ch in out)


def test_braille_ppi_fallbacks_to_polar_when_position_missing() -> None:
    r = BraillePpiRenderer(width_cells=12, height_cells=7, max_range_m=500.0)
    out = r.render_tracks([{"range_m": 0.0, "bearing_deg": 0.0}])
    assert any(ch != " " for ch in out)

