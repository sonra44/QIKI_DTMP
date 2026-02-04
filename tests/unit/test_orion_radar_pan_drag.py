import pytest


@pytest.mark.asyncio
async def test_orion_radar_pan_drag_updates_pan_signs() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    assert app._radar_pan_u_m == 0.0
    assert app._radar_pan_v_m == 0.0

    app._apply_radar_pan_from_drag(start_pan_u_m=0.0, start_pan_v_m=0.0, dx_cells=10, dy_cells=5)

    # Drag right should move the viewport right (tracks follow the drag), which
    # corresponds to negative pan_u due to u_m -= pan_u_m.
    assert app._radar_pan_u_m < 0.0
    # Drag down should move tracks down; that corresponds to positive pan_v.
    assert app._radar_pan_v_m > 0.0


@pytest.mark.asyncio
async def test_orion_radar_iso_drag_updates_yaw_pitch() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app._radar_view = "iso"
    yaw0 = float(app._radar_iso_yaw_deg)
    pitch0 = float(app._radar_iso_pitch_deg)

    app._apply_radar_drag_from_mouse(
        start_pan_u_m=0.0,
        start_pan_v_m=0.0,
        start_iso_yaw_deg=yaw0,
        start_iso_pitch_deg=pitch0,
        dx_cells=10,
        dy_cells=-5,
    )

    assert app._radar_iso_yaw_deg != yaw0
    assert app._radar_iso_pitch_deg != pitch0
