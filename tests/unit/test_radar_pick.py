from qiki.services.operator_console.radar.unicode_ppi import pick_nearest_track_id


def test_pick_nearest_track_top_view() -> None:
    tracks = [
        ("t-right", {"position": {"x": 100.0, "y": 0.0, "z": 0.0}}),
        ("t-left", {"position": {"x": -100.0, "y": 0.0, "z": 0.0}}),
    ]

    picked = pick_nearest_track_id(
        tracks,
        click_cell_x=11,
        click_cell_y=3,
        width_cells=12,
        height_cells=7,
        max_range_m=100.0,
        view="top",
        zoom=1.0,
    )
    assert picked == "t-right"


def test_pick_nearest_track_front_view_uses_y_axis() -> None:
    tracks = [
        ("t-front", {"position": {"x": 0.0, "y": 100.0, "z": 0.0}}),
        ("t-back", {"position": {"x": 0.0, "y": -100.0, "z": 0.0}}),
    ]

    picked = pick_nearest_track_id(
        tracks,
        click_cell_x=11,
        click_cell_y=3,
        width_cells=12,
        height_cells=7,
        max_range_m=100.0,
        view="front",
        zoom=1.0,
    )
    assert picked == "t-front"


def test_pick_returns_none_when_far() -> None:
    tracks = [("t-center", {"position": {"x": 0.0, "y": 0.0, "z": 0.0}})]

    picked = pick_nearest_track_id(
        tracks,
        click_cell_x=0,
        click_cell_y=0,
        width_cells=12,
        height_cells=7,
        max_range_m=100.0,
        view="top",
        zoom=1.0,
        pick_radius_cells=1.0,
    )
    assert picked is None
