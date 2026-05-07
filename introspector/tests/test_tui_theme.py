from __future__ import annotations

from project_introspector.operator_state import OperatorRunSummary, OperatorState
from project_introspector.tui_theme import operator_state_theme_class, status_theme_class


def test_status_theme_class_groups_operator_statuses() -> None:
    assert status_theme_class("completed") == "status-ok"
    assert status_theme_class("completed_with_limits") == "status-warning"
    assert status_theme_class("failed") == "status-error"
    assert status_theme_class("skipped") == "status-muted"
    assert status_theme_class("running") == "status-running"


def test_operator_state_theme_class_uses_run_status() -> None:
    state = OperatorState(
        run=OperatorRunSummary(
            run_id="run-theme",
            project_name="demo",
            mode="offline",
            status="completed_with_limits",
            source_root="src",
        ),
        layers=[],
        artifacts=[],
        modules=[],
        warnings=[],
        next_safe_steps=[],
    )

    assert operator_state_theme_class(state) == "status-warning"
    assert operator_state_theme_class(None) == "status-muted"
