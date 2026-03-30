import pytest


def test_orion_header_uses_compact_sim_label() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionHeader

    header = OrionHeader(id="orion-header")
    header.sim = "Running/Работает"

    class _FakeCell:
        def __init__(self) -> None:
            self.value = None
            self.tooltip = None

        def set_value(self, value: str, *, tooltip: str) -> None:
            self.value = value
            self.tooltip = tooltip

    cell_ids = [
        "hdr-online",
        "hdr-battery",
        "hdr-hull",
        "hdr-radiation",
        "hdr-t-ext",
        "hdr-t-core",
        "hdr-age",
        "hdr-freshness",
        "hdr-mode",
        "hdr-sim",
    ]
    cells = {cid: _FakeCell() for cid in cell_ids}

    # The header calls query_one() for each cell id; return our fakes.
    def _fake_query_one(selector: str, _cls=None):  # noqa: ANN001
        if not selector.startswith("#"):
            raise LookupError(selector)
        cid = selector[1:]
        if cid not in cells:
            raise LookupError(selector)
        return cells[cid]

    header.query_one = _fake_query_one  # type: ignore[method-assign]

    header._refresh_cells()

    sim_cell = cells["hdr-sim"]
    assert sim_cell.value is not None
    assert "Sim" in sim_cell.value
    assert "Сим" in sim_cell.value
    assert "Running" in sim_cell.value
    assert "Simulation" not in sim_cell.value
