from __future__ import annotations

from project_introspector.operator_state import OperatorLayerSummary, OperatorModuleRow, OperatorRunSummary, OperatorState
from project_introspector.tui_table_model import build_operator_module_table_rows, compact_module_path, format_signal_counts


def _state(*, runtime_events: int = 0) -> OperatorState:
    return OperatorState(
        run=OperatorRunSummary(run_id="run-table", project_name="demo", mode="offline", status="completed", source_root="src"),
        layers=[
            OperatorLayerSummary("runtime", "present" if runtime_events else "absent", {"runtime_event_count": runtime_events})
        ],
        artifacts=[],
        modules=[
            OperatorModuleRow(
                module_path="pkg.api",
                file_path="src/pkg/api.py",
                route_count=2,
                env_var_count=1,
                pydantic_model_count=1,
                class_attribute_count=3,
                enriched=True,
                degraded=False,
                findings_count=4,
            ),
            OperatorModuleRow(module_path="pkg.worker", file_path="src/pkg/worker.py"),
        ],
        warnings=[],
        next_safe_steps=[],
    )


def test_build_operator_module_table_rows_marks_selection() -> None:
    rows = build_operator_module_table_rows(_state(runtime_events=3), selected_module_path="pkg.api")

    assert rows[0].marker == ">"
    assert rows[0].module_path == "pkg.api"
    assert rows[0].signals == "routes:2 env:1 models:1 attrs:3"
    assert rows[0].enriched is True
    assert rows[0].findings_count == 4
    assert rows[0].state_kind == "warning"
    assert rows[1].marker == " "


def test_build_operator_module_table_rows_honors_limit() -> None:
    assert len(build_operator_module_table_rows(_state(), limit=1)) == 1
    assert build_operator_module_table_rows(_state(), limit=0) == []


def test_compact_module_path_and_signal_counts_are_datatable_ready() -> None:
    long_path = "very.long.package.name.with.many.parts.module"
    assert compact_module_path(long_path, max_len=24).startswith("...")
    assert format_signal_counts(OperatorModuleRow(module_path="pkg.empty", file_path="x.py")) == "-"

from project_introspector.tui_table_model import (
    filter_operator_modules,
    operator_module_table_headers,
    operator_module_table_row_values,
)


def _text(key: str, **kwargs: object) -> str:
    mapping = {
        "operator_module_table_col_selected": "Sel",
        "operator_module_table_col_module": "Module",
        "operator_module_table_col_state": "State",
        "operator_module_table_col_limits": "Limits",
        "operator_module_table_col_findings": "Findings",
        "operator_module_table_col_action": "Action",
        "operator_module_state_ready": "ready",
        "operator_module_state_limited": "partly ready",
        "operator_module_state_warning": "warning",
        "operator_module_limits_none": "none",
        "operator_module_limits_runtime": "no runtime",
        "operator_module_limits_enrichment": "no extra analysis",
        "operator_module_limits_runtime_and_enrichment": "no runtime, no extra analysis",
        "operator_module_action_none": "no action needed",
        "operator_module_action_collect_runtime": "collect runtime",
        "operator_module_action_run_enrichment": "run extra analysis",
        "operator_module_action_review_findings": "review findings",
    }
    return mapping[key].format(**kwargs) if kwargs else mapping[key]


def test_operator_module_table_headers_and_values_are_widget_ready() -> None:
    rows = build_operator_module_table_rows(_state(runtime_events=3), selected_module_path="pkg.api")

    assert operator_module_table_headers(_text) == ("Sel", "Module", "State", "Limits", "Findings", "Action")
    assert operator_module_table_row_values(_text, rows[0]) == (
        ">",
        "pkg.api",
        "warning",
        "none",
        "4",
        "review findings",
    )


def test_filter_operator_modules_supports_operator_filters() -> None:
    state = _state()

    assert [row.module_path for row in filter_operator_modules(state, search="worker")] == ["pkg.worker"]
    assert [row.module_path for row in filter_operator_modules(state, status_filter="routes")] == ["pkg.api"]
    assert [row.module_path for row in filter_operator_modules(state, status_filter="env-config")] == ["pkg.api"]
    assert [row.module_path for row in filter_operator_modules(state, status_filter="missing-enrichment")] == ["pkg.worker"]


def test_runtime_absent_maps_to_limited_not_ready() -> None:
    rows = build_operator_module_table_rows(_state())

    api = next(row for row in rows if row.raw_module_path == "pkg.api")
    assert api.state_kind == "warning"
    assert api.limits_kind == "runtime"
    assert api.next_action_kind == "collect_runtime"

    worker = next(row for row in rows if row.raw_module_path == "pkg.worker")
    assert worker.state_kind == "limited"
    assert worker.limits_kind == "runtime_and_enrichment"
    assert worker.next_action_kind == "collect_runtime"


def test_enrichment_absent_maps_to_limited_when_runtime_exists() -> None:
    rows = build_operator_module_table_rows(_state(runtime_events=3))

    worker = next(row for row in rows if row.raw_module_path == "pkg.worker")
    assert worker.state_kind == "limited"
    assert worker.limits_kind == "enrichment"
    assert worker.next_action_kind == "run_enrichment"


def test_attention_filter_includes_limited_not_only_degraded() -> None:
    state = _state(runtime_events=3)

    assert [row.module_path for row in filter_operator_modules(state, status_filter="needs-attention")] == [
        "pkg.api",
        "pkg.worker",
    ]


def test_ready_filter_requires_no_limits_or_findings() -> None:
    state = OperatorState(
        run=OperatorRunSummary(run_id="run-table", project_name="demo", mode="offline", status="completed", source_root="src"),
        layers=[OperatorLayerSummary("runtime", "present", {"runtime_event_count": 1})],
        artifacts=[],
        modules=[OperatorModuleRow(module_path="pkg.ready", file_path="src/pkg/ready.py", enriched=True)],
        warnings=[],
        next_safe_steps=[],
    )

    rows = build_operator_module_table_rows(state, status_filter="ready")
    assert len(rows) == 1
    assert rows[0].state_kind == "ready"
    assert rows[0].limits_kind == "none"
