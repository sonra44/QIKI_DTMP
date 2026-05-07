from __future__ import annotations

from project_introspector.tui_action_history import OperatorActionHistory
from project_introspector.tui_render import render_action_log
from project_introspector.tui_text import tui_text


def _text(key: str, **kwargs: object) -> str:
    return tui_text("en", key, **kwargs)


def test_action_history_updates_running_entry_on_finish() -> None:
    history = OperatorActionHistory(max_entries=10)

    history.start("scan-project", "Scan Project", message="starting", timestamp="2026-05-03T00:00:00Z")
    history.finish("scan-project", state="done", message="scan complete", timestamp="2026-05-03T00:00:02Z")

    assert len(history.entries) == 1
    entry = history.entries[0]
    assert entry.action_key == "scan-project"
    assert entry.state == "done"
    assert entry.started_at == "2026-05-03T00:00:00Z"
    assert entry.finished_at == "2026-05-03T00:00:02Z"


def test_action_history_trims_old_entries() -> None:
    history = OperatorActionHistory(max_entries=2)
    history.record("a", "A", "done", "first", started_at="2026-05-03T00:00:00Z")
    history.record("b", "B", "done", "second", started_at="2026-05-03T00:00:01Z")
    history.record("c", "C", "done", "third", started_at="2026-05-03T00:00:02Z")

    assert [entry.action_key for entry in history.entries] == ["b", "c"]


def test_render_action_log_prefers_persistent_history() -> None:
    history = OperatorActionHistory(max_entries=10)
    history.record("scan-project", "Scan Project", "done", "scan complete", started_at="2026-05-03T00:00:00Z")

    rendered = render_action_log(_text, {"scan-project": "stale snapshot"}, action_history=history.entries)

    assert "recent_actions" in rendered
    assert "Scan Project" in rendered
    assert "scan complete" in rendered
    assert "stale snapshot" not in rendered
