from __future__ import annotations

from dataclasses import asdict, dataclass

import httpx

from .models import ProjectSchema
from .operator_state import OperatorState, build_operator_state_from_analyzer_payloads
from .tui_client import IntrospectorTuiClient
from .tui_models import (
    AnalyzerStatus,
    LivePassSummary,
    ModuleAnalysisArtifact,
    ModuleOverviewRow,
    ProjectScanSummary,
    SubprocessResult,
)
from .tui_state import build_module_rows


class TuiOperationError(RuntimeError):
    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


@dataclass(slots=True)
class RefreshData:
    analyzer_status: AnalyzerStatus
    schema: ProjectSchema
    project_report: dict[str, object] | None
    analysis_map: dict[str, ModuleAnalysisArtifact]
    module_rows: list[ModuleOverviewRow]
    last_project_scan: ProjectScanSummary
    last_live_pass: LivePassSummary
    selected_module_path: str | None
    operator_state: OperatorState | None = None


@dataclass(slots=True)
class StatusReload:
    analyzer_status: AnalyzerStatus
    project_report: dict[str, object] | None
    last_project_scan: ProjectScanSummary
    last_live_pass: LivePassSummary
    operator_state: OperatorState | None = None


@dataclass(slots=True)
class ScanProjectResult:
    completed: SubprocessResult
    message: str
    last_project_scan: ProjectScanSummary


@dataclass(slots=True)
class LivePassResult:
    completed: SubprocessResult
    message: str
    last_live_pass: LivePassSummary


@dataclass(slots=True)
class ReanalyzeResult:
    module_path: str
    artifact: ModuleAnalysisArtifact


@dataclass(slots=True)
class ModuleViewsRefresh:
    analysis_map: dict[str, ModuleAnalysisArtifact]
    module_rows: list[ModuleOverviewRow]
    last_live_pass: LivePassSummary
    selected_module_path: str | None
    operator_state: OperatorState | None = None


class IntrospectorTuiOperations:
    def __init__(self, client: IntrospectorTuiClient) -> None:
        self.client = client

    @staticmethod
    def _raise_transport_error(action: str, exc: Exception) -> "TuiOperationError":
        detail = f"{type(exc).__name__}: {exc}"
        raise TuiOperationError(f"{action} failed", detail=detail) from exc

    def load_all_data(self, *, selected_module_path: str | None = None, force_refresh: bool = True) -> RefreshData:
        try:
            analyzer_status = self.client.fetch_status(force=force_refresh)
            schema = self.client.fetch_schema(force=force_refresh)
        except (httpx.HTTPError, OSError) as exc:
            self._raise_transport_error("initial refresh", exc)
        module_paths = [module.module_path for module in schema.modules]
        analysis_map = self.client.load_derived_analyses(
            module_paths,
            storage_layout=analyzer_status.storage_layout,
            force=force_refresh,
        )
        module_rows = build_module_rows(schema, analysis_map)
        project_report = self.client.fetch_report(force=force_refresh)
        last_project_scan = self.client.load_latest_project_scan(force=force_refresh)
        last_live_pass = self.client.load_latest_live_pass(force=force_refresh)
        operator_state = build_operator_state_from_analyzer_payloads(
            project_name=schema.project_name,
            schema=schema,
            report=project_report,
            llm_status=asdict(analyzer_status),
            scan_summary=asdict(last_project_scan),
            live_pass_summary=asdict(last_live_pass),
            analyses=analysis_map,
        )
        if selected_module_path and selected_module_path in {row.module_path for row in module_rows}:
            effective_selection = selected_module_path
        else:
            effective_selection = module_rows[0].module_path if module_rows else None
        return RefreshData(
            analyzer_status=analyzer_status,
            schema=schema,
            project_report=project_report,
            analysis_map=analysis_map,
            module_rows=module_rows,
            last_project_scan=last_project_scan,
            last_live_pass=last_live_pass,
            selected_module_path=effective_selection,
            operator_state=operator_state,
        )

    def reload_status(self, *, force_refresh: bool = True) -> StatusReload:
        try:
            analyzer_status = self.client.fetch_status(force=force_refresh)
        except (httpx.HTTPError, OSError) as exc:
            self._raise_transport_error("status reload", exc)
        project_report = self.client.fetch_report(force=force_refresh)
        last_project_scan = self.client.load_latest_project_scan(force=force_refresh)
        last_live_pass = self.client.load_latest_live_pass(force=force_refresh)
        latest_operator_state = self.client.load_latest_operator_state(force=force_refresh)
        return StatusReload(
            analyzer_status=analyzer_status,
            project_report=project_report,
            last_project_scan=last_project_scan,
            last_live_pass=last_live_pass,
            operator_state=latest_operator_state,
        )

    def run_project_scan(self) -> ScanProjectResult:
        completed = self.client.run_project_scan()
        output = completed.stdout.strip() or completed.stderr.strip() or "factual scan finished"
        if completed.timed_out:
            raise TuiOperationError(
                "factual scan timed out",
                detail=output or "subprocess timed out before it produced output",
            )
        if completed.returncode != 0:
            raise TuiOperationError(
                f"factual scan failed ({completed.returncode})",
                detail=output,
            )
        self.client.invalidate_schema_cache()
        self.client.invalidate_runtime_cache()
        return ScanProjectResult(
            completed=completed,
            message=output,
            last_project_scan=self.client.load_latest_project_scan(force=True),
        )

    def run_live_pass(self) -> LivePassResult:
        completed = self.client.run_live_pass()
        output = completed.stdout.strip() or completed.stderr.strip() or "enrichment queue finished"
        if completed.timed_out:
            raise TuiOperationError(
                "enrichment queue timed out",
                detail=output or "subprocess timed out before it produced output",
            )
        if completed.returncode != 0:
            raise TuiOperationError(
                f"enrichment queue failed ({completed.returncode})",
                detail=output,
            )
        self.client.invalidate_runtime_cache()
        self.client.invalidate_artifact_cache()
        return LivePassResult(
            completed=completed,
            message=output,
            last_live_pass=self.client.load_latest_live_pass(force=True),
        )

    def refresh_module_views(
        self,
        *,
        schema: ProjectSchema,
        storage_layout: dict[str, str] | None = None,
        selected_module_path: str | None = None,
    ) -> ModuleViewsRefresh:
        module_paths = [module.module_path for module in schema.modules]
        analysis_map = self.client.load_derived_analyses(
            module_paths,
            storage_layout=storage_layout,
            force=True,
        )
        module_rows = build_module_rows(schema, analysis_map)
        project_report = self.client.fetch_report(force=True)
        last_project_scan = self.client.load_latest_project_scan(force=True)
        last_live_pass = self.client.load_latest_live_pass(force=True)
        try:
            analyzer_status = self.client.fetch_status(force=False)
            operator_state = build_operator_state_from_analyzer_payloads(
                project_name=schema.project_name,
                schema=schema,
                report=project_report,
                llm_status=asdict(analyzer_status),
                scan_summary=asdict(last_project_scan),
                live_pass_summary=asdict(last_live_pass),
                analyses=analysis_map,
            )
        except Exception:
            operator_state = self.client.load_latest_operator_state(force=True)
        if selected_module_path and selected_module_path in {row.module_path for row in module_rows}:
            effective_selection = selected_module_path
        else:
            effective_selection = module_rows[0].module_path if module_rows else None
        return ModuleViewsRefresh(
            analysis_map=analysis_map,
            module_rows=module_rows,
            last_live_pass=last_live_pass,
            selected_module_path=effective_selection,
            operator_state=operator_state,
        )

    def reanalyze_module(
        self,
        module_path: str,
        *,
        storage_layout: dict[str, str] | None = None,
    ) -> ReanalyzeResult:
        try:
            analysis = self.client.fetch_module_analysis(module_path)
        except Exception as exc:  # pragma: no cover - exercised at app layer
            raise TuiOperationError(
                f"module re-analysis failed for {module_path}",
                detail=f"{type(exc).__name__}: {exc}",
            ) from exc
        self.client.invalidate_artifact_cache(module_path)
        artifact = self.client.load_module_artifact(
            module_path,
            storage_layout=storage_layout,
            analysis_override=analysis,
            force=True,
        )
        return ReanalyzeResult(module_path=module_path, artifact=artifact)
