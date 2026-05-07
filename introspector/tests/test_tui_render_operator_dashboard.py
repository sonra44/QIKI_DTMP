from __future__ import annotations

from project_introspector.operator_state import (
    OperatorArtifactSummary,
    OperatorLayerSummary,
    OperatorModuleRow,
    OperatorRunSummary,
    OperatorState,
)
from project_introspector.tui_render import render_operator_dashboard
from project_introspector.tui_text import tui_text


def test_render_operator_dashboard_summarizes_operator_state() -> None:
    state = OperatorState(
        run=OperatorRunSummary(
            run_id="run-1",
            project_name="demo",
            mode="offline",
            status="completed_with_limits",
            source_root="src",
        ),
        layers=[
            OperatorLayerSummary(name="factual", status="ready"),
            OperatorLayerSummary(name="runtime", status="absent"),
            OperatorLayerSummary(name="enrichment", status="skipped"),
            OperatorLayerSummary(name="report", status="skipped"),
        ],
        artifacts=[OperatorArtifactSummary(kind="schema", path="schema.json", required=True, exists=True)],
        modules=[OperatorModuleRow(module_path="pkg.api", file_path="src/pkg/api.py", route_count=1, enriched=True)],
        warnings=["runtime_absent"],
        next_safe_steps=["Review artifacts"],
    )

    rendered = render_operator_dashboard(lambda key, **kwargs: tui_text("en", key, **kwargs), state)

    assert "Operator overview" in rendered
    assert "Project: demo" in rendered
    assert "structure=structure ready" in rendered
    assert "routes=1" in rendered
    assert "Review artifacts" in rendered
    assert "runtime_absent" not in rendered
