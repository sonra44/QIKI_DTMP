import pytest


def test_orion_prefers_braille_ppi_renderer() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp
    from qiki.services.operator_console.radar.unicode_ppi import BraillePpiRenderer

    app = OrionApp()
    assert isinstance(app._ppi_renderer, BraillePpiRenderer)
