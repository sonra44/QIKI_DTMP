import pytest


def test_orion_summary_events_filters_show_off_when_unset() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app._events_filter_type = None
    app._events_filter_text = None

    blocks = app._build_summary_blocks()
    filters = [b for b in blocks if getattr(b, "block_id", None) == "events_filters"]
    assert len(filters) == 1
    b = filters[0]
    assert b.status == "ok"
    assert "type=" in str(b.value)
    assert "filter=" in str(b.value)
    assert "N/A" not in str(b.value)

