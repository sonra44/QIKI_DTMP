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
