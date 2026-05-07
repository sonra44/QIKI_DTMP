from __future__ import annotations

from pathlib import Path

from project_introspector.models import LLMModuleAnalysis
from project_introspector.tui_models import ModuleAnalysisArtifact
from project_introspector.tui_state import build_module_rows, compute_overview_stats, filter_module_rows


def test_build_module_rows_and_stats(introspector_modules) -> None:
    modules = [
        introspector_modules["project_introspector.runtime"],
        introspector_modules["project_introspector.tui_client"],
    ]
    from project_introspector.models import ProjectSchema, SymbolSummary

    schema = ProjectSchema(
        project_name="demo",
        module_count=len(modules),
        function_count=0,
        class_count=0,
        runtime_event_count=1,
        modules=modules,
        edges=[],
        symbols=[
            SymbolSummary(
                qualified_name="project_introspector.runtime.instrument_function",
                symbol_type="function",
                module_path="project_introspector.runtime",
                runtime_call_count=1,
                has_docstring=False,
            )
        ],
    )
    analyses = {
        "project_introspector.runtime": ModuleAnalysisArtifact(
            analysis=LLMModuleAnalysis(
                module_path="project_introspector.runtime",
                purpose="Instrument runtime functions",
                public_symbols=["project_introspector.runtime.instrument_function"],
                status="active",
                warnings=["missing module docstring"],
            ),
            artifact_path=Path("/tmp/main.json"),
        )
    }

    rows = build_module_rows(schema, analyses)
    stats = compute_overview_stats("demo", rows)

    assert rows[0].module_path == "project_introspector.runtime"
    assert rows[0].runtime_signal is True
    assert rows[1].status == "no-analysis"
    assert stats.module_count == 2
    assert stats.runtime_evidence_count == 1
    assert stats.warning_heavy_count == 1


def test_filter_module_rows_applies_search_and_runtime_filters() -> None:
    rows = [
        build_row("alpha.core", "active", False, 1, True, 2),
        build_row("beta.core", "stale-risk", False, 0, False, 0),
        build_row("gamma.core", "needs-attention", True, 2, False, 0),
    ]

    filtered = filter_module_rows(
        rows,
        search="core",
        status_filter="all",
        degraded_only=False,
        warnings_only=True,
        runtime_filter="runtime-only",
    )
    assert [row.module_path for row in filtered] == ["alpha.core"]

    stale = filter_module_rows(rows, runtime_filter="stale-risk-only")
    assert [row.module_path for row in stale] == ["beta.core"]


def build_row(module_path: str, status: str, degraded: bool, warnings_count: int, runtime_signal: bool, runtime_count: int):
    from project_introspector.tui_models import ModuleOverviewRow

    return ModuleOverviewRow(
        module_path=module_path,
        file_path=f"/tmp/{module_path}.py",
        status=status,
        enrichment_state="degraded" if degraded else "done",
        degraded=degraded,
        warnings_count=warnings_count,
        runtime_signal=runtime_signal,
        runtime_count=runtime_count,
        purpose="demo",
    )
