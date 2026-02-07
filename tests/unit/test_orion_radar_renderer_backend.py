import pytest


@pytest.mark.asyncio
async def test_radar_renderer_auto_falls_back_to_unicode_when_textual_image_missing(monkeypatch) -> None:
    pytest.importorskip("textual")

    monkeypatch.setenv("RADAR_RENDERER", "auto")
    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    assert app._radar_renderer_requested == "auto"
    assert app._radar_renderer_effective == "unicode"


@pytest.mark.asyncio
async def test_radar_renderer_kitty_falls_back_to_unicode_when_textual_image_missing(monkeypatch) -> None:
    pytest.importorskip("textual")

    monkeypatch.setenv("RADAR_RENDERER", "kitty")
    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    assert app._radar_renderer_requested == "kitty"
    assert app._radar_renderer_effective == "unicode"
