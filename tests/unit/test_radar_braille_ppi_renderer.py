from qiki.services.operator_console.radar.unicode_ppi import BraillePpiRenderer


def _first_non_space_cell(out: str) -> tuple[int, int] | None:
    lines = out.splitlines()
    for y, line in enumerate(lines):
        for x, ch in enumerate(line):
            if ch != " ":
                return (x, y)
    return None


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


def test_braille_ppi_top_view_projects_x_to_right() -> None:
    r = BraillePpiRenderer(width_cells=12, height_cells=7, max_range_m=100.0)
    out = r.render_tracks([{"position": {"x": 100.0, "y": 0.0, "z": 0.0}}], view="top")
    loc = _first_non_space_cell(out)
    assert loc is not None
    x, _y = loc
    assert x > (12 // 2)


def test_braille_ppi_side_view_projects_z_to_top() -> None:
    r = BraillePpiRenderer(width_cells=12, height_cells=7, max_range_m=100.0)
    out = r.render_tracks([{"position": {"x": 0.0, "y": 0.0, "z": 100.0}}], view="side")
    loc = _first_non_space_cell(out)
    assert loc is not None
    _x, y = loc
    assert y < (7 // 2)


def test_braille_ppi_front_view_projects_y_to_right() -> None:
    r = BraillePpiRenderer(width_cells=12, height_cells=7, max_range_m=100.0)
    out = r.render_tracks([{"position": {"x": 0.0, "y": 100.0, "z": 0.0}}], view="front")
    loc = _first_non_space_cell(out)
    assert loc is not None
    x, _y = loc
    assert x > (12 // 2)
