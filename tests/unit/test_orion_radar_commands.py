import pytest


def test_radar_renderer_auto_forces_unicode_in_ssh_tmux(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    import qiki.services.operator_console.main_orion as main_orion

    monkeypatch.setenv("RADAR_RENDERER", "auto")
    monkeypatch.setenv("TMUX", "/tmp/tmux-ssh-test")
    monkeypatch.setenv("SSH_CONNECTION", "1")

    # Ensure the test is actually checking the SSH+tmux policy (not missing deps fallbacks).
    monkeypatch.setattr(main_orion, "_textual_image_best_backend_kind", lambda: "kitty")
    monkeypatch.setattr(main_orion, "render_bitmap_ppi", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_orion, "RadarBitmapTGP", object())

    app = main_orion.OrionApp()
    assert app._radar_renderer_requested == "auto"
    assert app._radar_renderer_effective == "unicode"


def test_radar_view_hotkey_actions_update_state() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app.active_screen = "radar"

    app.action_radar_view_side()
    assert app._radar_view == "side"

    app.action_radar_view_front()
    assert app._radar_view == "front"

    app.action_radar_view_iso()
    assert app._radar_view == "iso"

    app.action_radar_view_top()
    assert app._radar_view == "top"


def test_radar_select_actions_cycle_tracks() -> None:
    pytest.importorskip("textual")

    import time

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app.active_screen = "radar"
    now = time.time()
    app._tracks_by_id = {
        "A": ({"range_m": 100.0, "bearing_deg": 0.0}, now),
        "B": ({"range_m": 200.0, "bearing_deg": 0.0}, now),
    }

    app.action_radar_select_next()
    assert app._selection_by_app["radar"].key == "A"

    app.action_radar_select_next()
    assert app._selection_by_app["radar"].key == "B"

    app.action_radar_select_prev()
    assert app._selection_by_app["radar"].key == "A"


@pytest.mark.asyncio
async def test_radar_overlay_command_toggles_vectors_and_labels() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app.active_screen = "radar"
    assert app._radar_overlay_vectors is True
    assert app._radar_overlay_labels is False

    await app._run_command("radar.overlay vectors off")
    assert app._radar_overlay_vectors is False

    await app._run_command("radar.overlay labels on")
    assert app._radar_overlay_labels is True

    await app._run_command("radar.overlay labels toggle")
    assert app._radar_overlay_labels is False


@pytest.mark.asyncio
async def test_radar_hotkeys_do_not_trigger_while_input_focused(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    import time

    import qiki.services.operator_console.main_orion as main_orion

    async def no_nats(self) -> None:  # noqa: ANN001
        self._boot_nats_init_done = True
        self._boot_nats_error = ""
        self.nats_client = None
        self.nats_connected = False

    monkeypatch.setattr(main_orion.OrionApp, "_init_nats", no_nats)

    app = main_orion.OrionApp()
    now = time.time()
    app._tracks_by_id = {
        "A": ({"range_m": 100.0, "bearing_deg": 0.0}, now),
        "B": ({"range_m": 200.0, "bearing_deg": 0.0}, now),
    }

    async with app.run_test(size=(140, 44)) as pilot:
        app.action_show_screen("radar")
        await pilot.pause()
        app._refresh_radar()
        await pilot.pause()
        app.action_focus_command()
        await pilot.pause()

        base_view = app._radar_view
        base_vectors = app._radar_overlay_vectors
        base_labels = app._radar_overlay_labels
        base_selection = app._selection_by_app.get("radar").key if "radar" in app._selection_by_app else None

        await pilot.press("1")
        await pilot.press("2")
        await pilot.press("3")
        await pilot.press("4")
        await pilot.press("n")
        await pilot.press("p")
        await pilot.press("k")
        await pilot.press("l")
        await pilot.pause()

        assert app._radar_view == base_view
        assert app._radar_overlay_vectors == base_vectors
        assert app._radar_overlay_labels == base_labels
        sel = app._selection_by_app.get("radar").key if "radar" in app._selection_by_app else None
        assert sel == base_selection


@pytest.mark.asyncio
async def test_radar_bitmap_render_error_falls_back_to_unicode(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    import qiki.services.operator_console.main_orion as main_orion
    from textual.widgets import Static

    class FakeBitmap(Static):
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001
            super().__init__(*args, **kwargs)
            self.image = None

    def boom(*args, **kwargs):  # noqa: ANN001
        raise RuntimeError("bitmap failed")

    async def no_nats(self) -> None:  # noqa: ANN001
        self._boot_nats_init_done = True
        self._boot_nats_error = ""
        self.nats_client = None
        self.nats_connected = False

    monkeypatch.setenv("RADAR_RENDERER", "kitty")
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    monkeypatch.setattr(main_orion.OrionApp, "_init_nats", no_nats)
    monkeypatch.setattr(main_orion, "render_bitmap_ppi", boom)
    monkeypatch.setattr(main_orion, "RadarBitmapTGP", FakeBitmap)

    app = main_orion.OrionApp()

    async with app.run_test(size=(140, 44)) as pilot:
        app.action_show_screen("radar")
        await pilot.pause()
        app._render_radar_ppi()
        await pilot.pause()
        assert app._radar_renderer_effective == "unicode"
        assert isinstance(app.query_one("#radar-ppi"), main_orion.RadarPpi)


@pytest.mark.asyncio
async def test_radar_legend_shows_selection_and_labels_lod(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    import time

    import qiki.services.operator_console.main_orion as main_orion

    async def no_nats(self) -> None:  # noqa: ANN001
        self._boot_nats_init_done = True
        self._boot_nats_error = ""
        self.nats_client = None
        self.nats_connected = False

    monkeypatch.setattr(main_orion.OrionApp, "_init_nats", no_nats)

    app = main_orion.OrionApp()
    now = time.time()
    app._tracks_by_id = {
        "AAAA": ({"range_m": 100.0, "bearing_deg": 0.0}, now),
    }

    async with app.run_test(size=(140, 44)) as pilot:
        app.action_show_screen("radar")
        await pilot.pause()

        app._radar_overlay_labels = True
        app._radar_zoom = 1.0
        app._refresh_radar()
        await pilot.pause()

        legend = app.query_one("#radar-legend")
        content = getattr(legend, "content", "")
        plain = content.plain if hasattr(content, "plain") else str(content)
        assert "AAAA" in plain
        assert "LBL:req" in plain

        app._radar_zoom = 3.0
        app._refresh_radar()
        await pilot.pause()
        content2 = getattr(legend, "content", "")
        plain2 = content2.plain if hasattr(content2, "plain") else str(content2)
        assert "LBL:req" not in plain2
        assert "LBL" in plain2


@pytest.mark.asyncio
async def test_radar_view_command_updates_state_without_forcing() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    assert app._radar_view == "top"

    await app._run_command("radar.view side")
    assert app._radar_view == "side"

    await app._run_command("radar.view front")
    assert app._radar_view == "front"

    await app._run_command("radar.view iso")
    assert app._radar_view == "iso"


@pytest.mark.asyncio
async def test_radar_zoom_command_updates_state() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    assert app._radar_zoom == 1.0

    await app._run_command("radar.zoom in")
    assert app._radar_zoom > 1.0

    await app._run_command("radar.zoom reset")
    assert app._radar_zoom == 1.0


@pytest.mark.asyncio
async def test_radar_pan_reset_command() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app._radar_pan_u_m = 10.0
    app._radar_pan_v_m = -20.0

    await app._run_command("radar.pan reset")
    assert app._radar_pan_u_m == 0.0
    assert app._radar_pan_v_m == 0.0


@pytest.mark.asyncio
async def test_radar_select_command_cycles_tracks() -> None:
    pytest.importorskip("textual")

    import time

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app.active_screen = "radar"
    now = time.time()
    app._tracks_by_id = {
        "A": ({"range_m": 100.0, "bearing_deg": 0.0}, now),
        "B": ({"range_m": 200.0, "bearing_deg": 0.0}, now),
    }

    await app._run_command("radar.select next")
    assert app._selection_by_app["radar"].key == "A"

    await app._run_command("radar.select next")
    assert app._selection_by_app["radar"].key == "B"

    await app._run_command("radar.select prev")
    assert app._selection_by_app["radar"].key == "A"


def test_unicode_ppi_vectors_and_labels_are_rendered() -> None:
    from qiki.services.operator_console.radar.unicode_ppi import BraillePpiRenderer

    r = BraillePpiRenderer(width_cells=24, height_cells=10, max_range_m=1000.0)
    payload = {
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "velocity": {"x": 10.0, "y": 0.0, "z": 0.0},
        "iff": "FRIEND",
    }

    base = r.render_tracks([("ABCD", payload)], view="top", zoom=3.0, draw_overlays=False, rich=False)
    with_vec = r.render_tracks(
        [("ABCD", payload)],
        view="top",
        zoom=3.0,
        draw_overlays=False,
        draw_vectors=True,
        rich=False,
    )
    with_lbl = r.render_tracks(
        [("ABCD", payload)],
        view="top",
        zoom=3.0,
        draw_overlays=False,
        draw_labels=True,
        rich=False,
    )

    def count_marks(s: str) -> int:
        return sum(1 for ch in s if ch not in {" ", "\n"})

    assert isinstance(base, str)
    assert isinstance(with_vec, str)
    assert isinstance(with_lbl, str)
    assert count_marks(with_vec) > count_marks(base)
    assert "ABCD" in with_lbl


def test_pick_radius_scales_with_zoom() -> None:
    from qiki.services.operator_console.radar.unicode_ppi import pick_nearest_track_id

    width_cells = 20
    height_cells = 10
    click_center_x = width_cells // 2
    click_center_y = height_cells // 2
    tracks = [("A", {"position": {"x": 0.0, "y": 0.0, "z": 0.0}})]

    picked_low = pick_nearest_track_id(
        tracks,
        click_cell_x=click_center_x + 2,
        click_cell_y=click_center_y,
        width_cells=width_cells,
        height_cells=height_cells,
        max_range_m=1000.0,
        view="top",
        zoom=1.0,
    )
    assert picked_low == "A"

    picked_high = pick_nearest_track_id(
        tracks,
        click_cell_x=click_center_x + 2,
        click_cell_y=click_center_y,
        width_cells=width_cells,
        height_cells=height_cells,
        max_range_m=1000.0,
        view="top",
        zoom=9.0,
    )
    assert picked_high is None


@pytest.mark.asyncio
async def test_radar_iso_reset_command() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app._radar_view = "iso"
    app._radar_iso_yaw_deg = 10.0
    app._radar_iso_pitch_deg = -10.0

    await app._run_command("radar.iso reset")
    assert app._radar_iso_yaw_deg == 45.0
    assert app._radar_iso_pitch_deg == 35.0


@pytest.mark.asyncio
async def test_radar_iso_rotate_command_updates_yaw_pitch() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    assert app._radar_iso_yaw_deg == 45.0
    assert app._radar_iso_pitch_deg == 35.0

    await app._run_command("radar.iso rotate 10 -5")
    assert app._radar_iso_yaw_deg == 55.0
    assert app._radar_iso_pitch_deg == 30.0


@pytest.mark.asyncio
async def test_mouse_on_off_commands_do_not_crash() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    await app._run_command("mouse on")
    await app._run_command("mouse off")


@pytest.mark.asyncio
async def test_mouse_debug_on_off_commands_do_not_crash() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    await app._run_command("mouse debug on")
    assert app._mouse_debug is True
    await app._run_command("mouse debug off")
    assert app._mouse_debug is False


@pytest.mark.asyncio
async def test_output_follow_and_scroll_commands_update_state() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    assert app._output_follow is True

    await app._run_command("output follow off")
    assert app._output_follow is False

    await app._run_command("output end")
    assert app._output_follow is True

    await app._run_command("output up 5")
    assert app._output_follow is False
