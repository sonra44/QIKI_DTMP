import pytest


def test_orion_summary_events_filters_show_off_when_unset_verbose_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    monkeypatch.setenv("ORION_SUMMARY_COMPACT_DEFAULT", "0")
    app = OrionApp()
    app._events_filter_type = None
    app._events_filter_text = None

    blocks = app._build_summary_blocks()
    actions = [b for b in blocks if getattr(b, "block_id", None) == "actions_incidents"]
    assert len(actions) == 1
    b = actions[0]
    assert b.status in {"na", "ok", "warn"}
    assert "trust=off" in str(b.value)
