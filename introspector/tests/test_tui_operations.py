from __future__ import annotations

from pathlib import Path

import pytest

from project_introspector.models import LLMModuleAnalysis, ProjectSchema
from project_introspector.tui_models import (
    AnalyzerStatus,
    LivePassSummary,
    ModuleAnalysisArtifact,
    ProjectScanSummary,
    SubprocessResult,
)
from project_introspector.tui_operations import IntrospectorTuiOperations, TuiOperationError


class OperationsClient:
    def __init__(self, introspector_modules) -> None:
        self._modules = [
            introspector_modules["project_introspector.runtime"],
            introspector_modules["project_introspector.tui_client"],
        ]
        self.fetch_schema_calls = 0
        self.load_latest_live_pass_calls = 0
        self.load_latest_project_scan_calls = 0
        self.load_derived_calls = 0

    def fetch_status(self, *, force: bool = False) -> AnalyzerStatus:
        return AnalyzerStatus(
            configured=True,
            base_url="http://127.0.0.1:8015",
            default_model="normal",
            fallback_model="cheap",
            app_name="project-introspector",
            build_marker=None,
            app_file="/tmp/analyzer/app.py",
            storage_layout={"derived": "/tmp/derived"},
        )

    def fetch_schema(self, *, force: bool = False) -> ProjectSchema:
        self.fetch_schema_calls += 1
        return ProjectSchema(
            project_name="demo",
            module_count=len(self._modules),
            function_count=0,
            class_count=0,
            runtime_event_count=0,
            modules=self._modules,
            edges=[],
            symbols=[],
        )

    def fetch_report(self, *, force: bool = False):
        return {
            "scope": {"project_name": "demo", "source_root": "/tmp/src"},
            "factual_layer": {"modules_scanned": 2, "scan_errors": 0},
            "runtime_layer": {"status": "absent", "runtime_event_count": 0},
            "enrichment_layer": {"status": "absent", "provider_configured": False},
            "module_findings_total": 0,
            "limits": [{"code": "runtime_absent"}],
            "next_safe_steps": ["Run runtime evidence."],
            "provenance": {"llm_is_truth_source": False},
        }

    def load_derived_analyses(self, module_paths, *, storage_layout=None, force: bool = False):
        self.load_derived_calls += 1
        return {
            module_path: ModuleAnalysisArtifact(
                analysis=LLMModuleAnalysis(module_path=module_path, status="active"),
                artifact_path=Path(f"/tmp/{module_path}.json"),
            )
            for module_path in module_paths
        }

    def load_latest_live_pass(self, *, force: bool = False) -> LivePassSummary:
        self.load_latest_live_pass_calls += 1
        return LivePassSummary(summary_path=Path("/tmp/summary.json"))

    def load_latest_project_scan(self, *, force: bool = False) -> ProjectScanSummary:
        self.load_latest_project_scan_calls += 1
        return ProjectScanSummary(summary_path=Path("/tmp/project_scan_summary.json"), modules_scanned=2, scan_errors=0)

    def run_project_scan(self) -> SubprocessResult:
        return SubprocessResult(returncode=0, stdout="scan ok", stderr="")

    def run_live_pass(self) -> SubprocessResult:
        return SubprocessResult(
            returncode=1,
            stdout="",
            stderr="provider unavailable",
        )

    def fetch_module_analysis(self, module_path: str, *, cheap_mode: bool = False) -> LLMModuleAnalysis:
        return LLMModuleAnalysis(module_path=module_path, purpose="fresh", status="active")

    def load_module_artifact(self, module_path: str, *, storage_layout=None, analysis_override=None):
        return ModuleAnalysisArtifact(
            analysis=analysis_override,
            artifact_path=Path(f"/tmp/{module_path}.json"),
        )

    def invalidate_runtime_cache(self) -> None:
        return None

    def invalidate_schema_cache(self) -> None:
        return None

    def invalidate_artifact_cache(self, module_path: str | None = None) -> None:
        return None


def test_load_all_data_preserves_requested_selection(introspector_modules) -> None:
    operations = IntrospectorTuiOperations(OperationsClient(introspector_modules))

    result = operations.load_all_data(selected_module_path="project_introspector.tui_client")

    assert result.selected_module_path == "project_introspector.tui_client"
    assert len(result.module_rows) == 2
    assert result.project_report is not None


def test_run_live_pass_raises_structured_error(introspector_modules) -> None:
    operations = IntrospectorTuiOperations(OperationsClient(introspector_modules))

    with pytest.raises(TuiOperationError) as excinfo:
        operations.run_live_pass()

    assert excinfo.value.message == "enrichment queue failed (1)"
    assert excinfo.value.detail == "provider unavailable"


def test_run_project_scan_returns_summary(introspector_modules) -> None:
    operations = IntrospectorTuiOperations(OperationsClient(introspector_modules))

    result = operations.run_project_scan()

    assert result.message == "scan ok"
    assert result.last_project_scan.modules_scanned == 2


def test_run_live_pass_surfaces_timeout(introspector_modules) -> None:
    class TimeoutClient(OperationsClient):
        def run_live_pass(self) -> SubprocessResult:
            return SubprocessResult(
                returncode=124,
                stdout="",
                stderr="timeout",
                timed_out=True,
            )

    operations = IntrospectorTuiOperations(TimeoutClient(introspector_modules))

    with pytest.raises(TuiOperationError) as excinfo:
        operations.run_live_pass()

    assert excinfo.value.message == "enrichment queue timed out"
    assert excinfo.value.detail == "timeout"


def test_refresh_module_views_reuses_existing_schema(introspector_modules) -> None:
    client = OperationsClient(introspector_modules)
    operations = IntrospectorTuiOperations(client)
    schema = client.fetch_schema()

    result = operations.refresh_module_views(
        schema=schema,
        storage_layout={"derived": "/tmp/derived"},
        selected_module_path="project_introspector.tui_client",
    )

    assert result.selected_module_path == "project_introspector.tui_client"
    assert len(result.module_rows) == 2
    assert client.fetch_schema_calls == 1
    assert client.load_derived_calls == 1
    assert client.load_latest_live_pass_calls == 1
