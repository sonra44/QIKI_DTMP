import pytest


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

