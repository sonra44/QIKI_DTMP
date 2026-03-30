import pytest


def test_orion_events_seed_row_has_clear_message() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp
    from qiki.services.operator_console.ui import i18n as I18N

    app = OrionApp()

    captured = {}

    class _FakeDataTable:
        id = "events-table"

        def clear(self) -> None:
            return

        def add_row(self, *_cells, key: str | None = None) -> None:  # noqa: ANN001
            if key is not None:
                captured[str(key)] = list(_cells)

    def _fake_query_one(selector, _cls=None):  # noqa: ANN001
        if selector == "#events-table":
            return _FakeDataTable()
        raise LookupError(selector)

    app.query_one = _fake_query_one  # type: ignore[method-assign]

    app._seed_events_table()

    assert "seed" in captured
    cells = captured["seed"]
    assert I18N.bidi("No events yet", "Событий нет") in str(cells)
