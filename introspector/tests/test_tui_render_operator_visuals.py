from __future__ import annotations

from project_introspector.operator_state import (
    OperatorArtifactSummary,
    OperatorLayerSummary,
    OperatorModuleRow,
    OperatorRunSummary,
    OperatorState,
)
from project_introspector.tui_render import (
    render_action_log,
    render_operator_health_cards,
    render_operator_inspector,
    render_operator_module_table,
)
from project_introspector.tui_text import tui_text


def _text(key: str, **kwargs: object) -> str:
    return tui_text("en", key, **kwargs)


def _state() -> OperatorState:
    return OperatorState(
        run=OperatorRunSummary(
            run_id="run-visual",
            project_name="demo",
            mode="offline",
            status="completed_with_limits",
            source_root="src",
        ),
        layers=[
            OperatorLayerSummary(
                name="factual",
                status="ready",
                details={"modules_scanned": 2, "scan_errors": 0, "schema_ready": True},
            ),
            OperatorLayerSummary(name="runtime", status="absent", details={"runtime_event_count": 0}),
            OperatorLayerSummary(
                name="enrichment",
                status="skipped",
                details={"provider_configured": False, "modules_done": 1, "degraded_count": 1},
            ),
            OperatorLayerSummary(name="report", status="skipped", details={"report_path": None}),
        ],
        artifacts=[OperatorArtifactSummary(kind="schema", path="schema.json", required=True, exists=True)],
        modules=[
            OperatorModuleRow(
                module_path="pkg.api",
                file_path="src/pkg/api.py",
                route_count=2,
                env_var_count=1,
                cli_option_count=0,
                pydantic_model_count=1,
                class_attribute_count=3,
                enriched=True,
                degraded=True,
                findings_count=2,
            ),
            OperatorModuleRow(module_path="pkg.worker", file_path="src/pkg/worker.py"),
        ],
        warnings=["runtime_absent"],
        next_safe_steps=["Review artifacts"],
    )


def test_render_operator_health_cards_shows_layer_details() -> None:
    rendered = render_operator_health_cards(_text, _state())

    assert "Data readiness" in rendered
    assert "structure ready" in rendered
    assert "modules checked=2" in rendered
    assert "execution data missing" in rendered
    assert "runtime_absent" not in rendered
    assert "provider_configured" not in rendered


def test_render_operator_module_table_marks_selected_module() -> None:
    rendered = render_operator_module_table(_text, _state(), selected_module_path="pkg.api")

    assert "Module" in rendered
    assert "> pkg.api" in rendered
    assert "warning" in rendered
    assert "no runtime" in rendered
    assert "collect runtime" in rendered


def test_render_operator_inspector_handles_selection_and_empty_selection() -> None:
    selected = render_operator_inspector(_text, _state(), "pkg.api")
    empty = render_operator_inspector(_text, _state(), None)

    assert "Module card" in selected
    assert "module=pkg.api" in selected
    assert "findings=2" in selected
    assert "enriched=" not in selected
    assert "degraded=" not in selected
    assert "select a module" in empty
    assert "Review artifacts" in empty


def test_render_action_log_shows_running_state_and_hotkeys() -> None:
    rendered = render_action_log(
        _text,
        {"scan-project": "done", "live-pass": "queued"},
        running_actions={"live-pass"},
    )

    assert "action_log" in rendered
    assert "scan-project: done" in rendered
    assert "live-pass: running" in rendered
    assert "ctrl+q quit" in rendered


def test_operator_visual_text_has_russian_keys() -> None:
    rendered = render_operator_health_cards(lambda key, **kwargs: tui_text("ru", key, **kwargs), _state())

    assert "Готовность данных" in rendered
    assert "Ограничения=1" in rendered
    assert "нет данных исполнения" in rendered
