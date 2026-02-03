import pytest


def test_orion_ppi_scope_renderer_available_and_renders() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.ui.charts import PpiScopeRenderer

    renderer = PpiScopeRenderer(width=11, height=7, max_range_m=100.0)
    out = renderer.render_tracks([{"range_m": 0.0, "bearing_deg": 0.0}])

    assert isinstance(out, str)
    # Basic structural expectations: multi-line scope with a center mark.
    assert "\n" in out
    assert ("+" in out) or ("●" in out)
