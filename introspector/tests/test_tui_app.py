from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")
from copy import deepcopy
from pathlib import Path

import httpx
from project_introspector.models import LLMModuleAnalysis, ProjectSchema, SymbolSummary
from project_introspector.tui_app import IntrospectorTuiApp, _mouse_enabled_from_env
from project_introspector.tui_render import render_analysis_guide, render_replay_status
from project_introspector.tui_text import localize_free_text, localize_semantic_text, tui_text
from project_introspector.tui_models import (
    AnalyzerStatus,
    ArtifactReference,
    LivePassSummary,
    ModuleAnalysisArtifact,
    ModuleOverviewRow,
    ProjectScanSummary,
)
from textual.widgets import Button, Input


class FakeTuiClient:
    def __init__(self, introspector_modules) -> None:
        modules = [
            introspector_modules["project_introspector.runtime"],
            introspector_modules["project_introspector.tui_client"],
            introspector_modules["project_introspector.tui_app"],
        ]
        self.status = AnalyzerStatus(
            configured=False,
            base_url="http://127.0.0.1:8015",
            default_model="normal",
            fallback_model="cheap",
            app_name="project-introspector",
            build_marker="test-build",
            app_file="/tmp/analyzer/app.py",
            storage_layout={"static": "/tmp/static", "runtime": "/tmp/runtime", "derived": "/tmp/derived"},
        )
        self.schema = ProjectSchema(
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
        self.analyses = {
            module.module_path: ModuleAnalysisArtifact(
                analysis=LLMModuleAnalysis(
                    module_path=module.module_path,
                    purpose=f"purpose for {module.module_path}",
                    responsibilities=["one", "two"],
                    public_symbols=[module.module_path + ".Symbol"],
                    status="active" if module.module_path.endswith(".runtime") else "stale-risk",
                    actionable_hints=["hint"],
                    warnings=["warning"] if module.module_path.endswith(".tui_client") else [],
                    processing_notes=["note"],
                    degraded=False,
                ),
                artifact_path=Path(f"/tmp/{module.module_path}.json"),
                detail_ref=ArtifactReference(
                    path=Path(f"/tmp/{module.module_path}.json"),
                    source_kind="derived",
                    variant="unknown",
                    updated_at="2026-04-04T00:00:00+00:00",
                    exists=True,
                ),
                related_refs=[
                    ArtifactReference(
                        path=Path(f"/tmp/{module.module_path}_cheap.json"),
                        source_kind="live-replay",
                        variant="cheap",
                        updated_at="2026-04-04T00:01:00+00:00",
                        exists=True,
                    )
                ],
            )
            for module in modules
        }
        self.fetch_schema_calls = 0
        self.project_scan_runs = 0

    def fetch_status(self, *, force: bool = False):
        return self.status

    def fetch_schema(self, *, force: bool = False):
        self.fetch_schema_calls += 1
        return self.schema

    def fetch_report(self, *, force: bool = False):
        return {
            "scope": {"project_name": "demo", "source_root": "/tmp/src"},
            "factual_layer": {
                "modules_scanned": 3,
                "scan_errors": 0,
                "function_count": 10,
                "class_count": 2,
                "symbol_count": 12,
                "import_edge_count": 5,
            },
            "runtime_layer": {"status": "present", "runtime_event_count": 1},
            "enrichment_layer": {
                "status": "degraded",
                "provider_configured": False,
                "modules_done": 2,
                "modules_degraded": 1,
                "modules_failed": 0,
            },
            "module_findings_total": 3,
            "module_findings": [
                {
                    "module_path": "project_introspector.tui_client",
                    "purpose": "client report bridge",
                    "status": "active",
                    "degraded": True,
                    "warnings": ["provider unavailable"],
                    "actionable_hints": ["retry enrichment later"],
                    "provenance": {
                        "doc_key": "ops_live_module_project_introspector__tui_client",
                        "trust_layer": "llm_enrichment",
                    },
                }
            ],
            "limits": [{"code": "enrichment_degraded"}],
            "next_safe_steps": ["Review factual counts before enrichment."],
            "provenance": {"llm_is_truth_source": False},
        }

    def load_derived_analyses(self, module_paths, *, storage_layout=None, force: bool = False):
        return {module_path: self.analyses[module_path] for module_path in module_paths}

    def load_latest_live_pass(self, *, force: bool = False):
        return LivePassSummary(summary_path=Path("/tmp/summary.json"), artifact_paths=[Path("/tmp/main.json")])

    def load_latest_project_scan(self, *, force: bool = False):
        return ProjectScanSummary(
            summary_path=Path("/tmp/project_scan_summary.json"),
            project_name="demo",
            source_root="/tmp/src",
            modules_scanned=3,
            scan_errors=0,
            scanned_at="2026-04-04T00:00:00+00:00",
            output_dir="/tmp/project_scan",
        )

    def run_project_scan(self):
        self.project_scan_runs += 1
        return type("Result", (), {"returncode": 0, "stdout": "scan done", "stderr": "", "timed_out": False})()

    def run_live_pass(self):  # pragma: no cover
        raise AssertionError("not expected in smoke test")

    def fetch_module_analysis(self, module_path: str, *, cheap_mode: bool = False):  # pragma: no cover
        return self.analyses[module_path].analysis

    def derived_artifact_path(self, module_path: str, *, storage_layout=None) -> Path:
        return Path(f"/tmp/{module_path}.json")

    def invalidate_runtime_cache(self) -> None:
        return None

    def invalidate_schema_cache(self) -> None:
        return None

    def invalidate_artifact_cache(self, module_path: str | None = None) -> None:
        return None


def _row(module_path: str, enrichment_state: str) -> ModuleOverviewRow:
    return ModuleOverviewRow(
        module_path=module_path,
        file_path=f"/tmp/{module_path}.py",
        status="active",
        enrichment_state=enrichment_state,
        degraded=False,
        warnings_count=0,
        runtime_signal=False,
        runtime_count=0,
        purpose="-",
    )


def test_tui_app_smoke(introspector_modules) -> None:
    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            top_status = str(app.query_one("#top-status").visual)
            replay_status = str(app.query_one("#replay-status").visual)
            assert "project=demo" in top_status
            assert "scan=schema_loaded" in top_status
            assert "analysis source=unconfigured" in top_status
            assert "operator_next: review enriched module evidence and freshness" in replay_status
            guide = str(app.query_one("#analysis-guide").visual)
            assert "ANALYSIS GUIDE" in guide
            assert "ANALYZER-BACKED SCAN" in guide
            assert "VALIDATION RESULT" in guide
            assert "NOT AVAILABLE WITHOUT LLM OR CODE CHANGES" in guide
            overview_table = str(app.query_one("#overview-table").visual)
            assert "project_introspector.runtime" in overview_table
            assert "project_introspector.tui_client" in overview_table
            assert "project_introspector.tui_app" in overview_table

    asyncio.run(run_smoke())


def test_render_analysis_guide_is_actionable_in_both_languages() -> None:
    en = render_analysis_guide(lambda key, **kwargs: tui_text("en", key, **kwargs))
    ru = render_analysis_guide(lambda key, **kwargs: tui_text("ru", key, **kwargs))

    assert "project-introspector run" in en
    assert "run_result.json" in en
    assert "schema_ready" in en
    assert "runtime_events" in en
    assert "QIKI canon" in en
    assert "project-introspector run" in ru
    assert "run_result.json" in ru
    assert "schema_ready" in ru
    assert "runtime_events" in ru
    assert "QIKI canon" in ru


def test_tui_analysis_guide_renders_when_analyzer_is_down(introspector_modules) -> None:
    class ErrorClient(FakeTuiClient):
        def fetch_status(self, *, force: bool = False):
            raise RuntimeError("analyzer down")

    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=ErrorClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            top_status = str(app.query_one("#top-status").visual)
            guide = str(app.query_one("#analysis-guide").visual)
            assert "analyzer down" in top_status
            assert "ANALYSIS GUIDE" in guide
            assert "ANALYZER-BACKED SCAN" in guide
            assert "VALIDATION RESULT" in guide

    asyncio.run(run_smoke())


def test_tui_initial_tab_can_open_analysis_guide(introspector_modules, monkeypatch) -> None:
    monkeypatch.setenv("INTROSPECTOR_TUI_INITIAL_TAB", "guide")

    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#main-tabs").active == "analysis-guide-pane"
            assert "guide-panel" in app.query_one("#analysis-guide").classes
            assert "guide-kicker" in app.query_one("#analysis-guide-kicker").classes
            assert "operator checklist" in str(app.query_one("#analysis-guide-kicker").visual)
            guide = str(app.query_one("#analysis-guide").visual)
            assert "ANALYSIS GUIDE" in guide

    asyncio.run(run_smoke())


def test_replay_status_operator_next_branches() -> None:
    text = IntrospectorTuiApp()._text
    base_status = AnalyzerStatus(configured=False, app_name="project-introspector")
    pending_rows = [_row("project_introspector.runtime", "pending")]
    done_rows = [_row("project_introspector.runtime", "done")]

    no_scan = render_replay_status(
        text,
        base_status,
        None,
        None,
        schema_ready=True,
        runtime_merged=False,
        module_rows=pending_rows,
        action_hint="",
    )
    assert "operator_next: run factual scan first" in no_scan

    scan_waiting_provider = render_replay_status(
        text,
        base_status,
        ProjectScanSummary(factual_status="done", modules_scanned=1),
        None,
        schema_ready=True,
        runtime_merged=False,
        module_rows=pending_rows,
        action_hint="",
    )
    assert "operator_next: factual scan is ready; configure provider before enrichment" in scan_waiting_provider

    provider_ready = render_replay_status(
        text,
        AnalyzerStatus(configured=True, app_name="project-introspector"),
        ProjectScanSummary(factual_status="done", modules_scanned=1),
        None,
        schema_ready=True,
        runtime_merged=False,
        module_rows=pending_rows,
        action_hint="",
    )
    assert "operator_next: run enrichment queue or enrich selected module" in provider_ready

    reviewable = render_replay_status(
        text,
        base_status,
        ProjectScanSummary(factual_status="done", modules_scanned=1),
        LivePassSummary(enrichment_status="done", modules_done=1),
        schema_ready=True,
        runtime_merged=False,
        module_rows=done_rows,
        action_hint="",
    )
    assert "operator_next: review enriched module evidence and freshness" in reviewable


def test_tui_project_report_overview_is_read_only_and_layered(introspector_modules) -> None:
    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            report = str(app.query_one("#project-report").visual)
            assert "Report snapshot: demo" in report
            assert "Source root: /tmp/src" in report
            assert "Structure: modules=3 | scan errors=0 | code objects=12 | import links=5" in report
            assert "Execution data: execution data collected | events=1" in report
            assert "Extra analysis: extra analysis limited | source not configured" in report
            assert "Limitations: extra analysis limited" in report
            assert "Next step: Review factual counts before enrichment." in report
            assert "provider_configured" not in report
            findings = str(app.query_one("#project-findings").visual)
            assert "Module findings: 1/3" in findings
            assert "client report bridge" in findings
            assert "provider unavailable" in findings
            assert "retry enrichment later" in findings
            assert "trust_layer=llm_enrichment" in findings
            replay_report = str(app.query_one("#replay-project-report").visual)
            assert "Project report:" in replay_report
            assert "Structural scan:" in replay_report
            assert "Module findings preview:" in replay_report
            assert "project_introspector.tui_client" in replay_report
            assert "source=ops_live_module_project_introspector__tui_client" in replay_report
            assert "LLM is truth source: false" in replay_report
            replay_findings = str(app.query_one("#replay-project-findings").visual)
            assert "Module findings: 1/3" in replay_findings

    asyncio.run(run_smoke())


def test_tui_project_report_handles_missing_and_malformed_payload_fields(introspector_modules) -> None:
    class PartialReportClient(FakeTuiClient):
        def fetch_report(self, *, force: bool = False):
            return {
                "factual_layer": {
                    "modules_scanned": 3,
                    "scan_errors": 0,
                },
                "runtime_layer": {},
                "enrichment_layer": {
                    "status": "degraded",
                    "provider_configured": False,
                },
                "module_findings_total": 5,
                "module_findings": "malformed",
                "limits": "malformed",
                "next_safe_steps": [],
                "provenance": {},
            }

    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=PartialReportClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            report = str(app.query_one("#project-report").visual)
            assert "Report snapshot: unknown" in report
            assert "Source root: unknown" in report
            assert "Structure: modules=3 | scan errors=0 | code objects=0 | import links=0" in report
            assert "Execution data: execution data not collected | events=0" in report
            assert "Extra analysis: extra analysis limited | source not configured" in report
            assert "Limitations: none" in report
            assert "Next step: unknown" in report
            findings = str(app.query_one("#project-findings").visual)
            assert "Module findings: 0/5" in findings

    asyncio.run(run_smoke())


def test_tui_project_report_handles_missing_finding_provenance(introspector_modules) -> None:
    class MissingProvenanceClient(FakeTuiClient):
        def fetch_report(self, *, force: bool = False):
            report = deepcopy(super().fetch_report(force=force))
            report["module_findings"] = [
                {
                    "module_path": "pkg.partial",
                    "purpose": "partial enrichment output",
                    "status": "stale-risk",
                    "degraded": True,
                    "warnings": "malformed",
                    "actionable_hints": "malformed",
                }
            ]
            report["module_findings_total"] = 1
            return report

    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=MissingProvenanceClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            report = str(app.query_one("#project-report").visual)
            assert "Report snapshot: demo" in report
            assert "Source root: /tmp/src" in report
            assert "pkg.partial" not in report
            findings = str(app.query_one("#project-findings").visual)
            assert "Module findings: 1/1" in findings
            assert "pkg.partial" in findings
            assert "partial enrichment output" in findings
            assert "provenance=unknown | trust_layer=unknown" in findings
            assert "warnings=0" in findings
            replay_report = str(app.query_one("#replay-project-report").visual)
            assert "pkg.partial" in replay_report
            assert "source=unknown" in replay_report

    asyncio.run(run_smoke())


def test_tui_project_findings_follow_overview_filters(introspector_modules) -> None:
    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#overview-search", Input).value = "runtime"
            await pilot.pause()
            findings = str(app.query_one("#project-findings").visual)
            assert "Module findings: 0/3" in findings
            assert "client report bridge" not in findings
            app.query_one("#overview-search", Input).value = "tui_client"
            await pilot.pause()
            findings = str(app.query_one("#project-findings").visual)
            assert "Module findings: 1/3" in findings
            assert "client report bridge" in findings
            await app.action_toggle_warnings()
            findings = str(app.query_one("#project-findings").visual)
            assert "Module findings: 1/3" in findings

    asyncio.run(run_smoke())


def test_tui_language_toggle_updates_visible_controls(introspector_modules) -> None:
    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            language_button = app.query_one("#btn-language", Button)
            assert str(language_button.label) == "RU/EN (t): EN"
            assert str(language_button.tooltip) == "Switch the interface language between English and Russian."
            await pilot.click("#btn-language")
            await pilot.pause()
            assert str(language_button.label) == "RU/EN (t): RU"
            assert str(language_button.tooltip) == "Переключает язык интерфейса между русским и английским."
            assert app.query_one("#overview-search", Input).placeholder == "Поиск по пути модуля"
            assert str(app.query_one("#overview-search", Input).tooltip) == "Фильтрует таблицу обзора по пути модуля."
            assert "Карточка модуля" in str(app.query_one("#module-details-title").visual)
            assert str(app.query_one("#btn-scan-project", Button).label) == "Сканировать проект"

    asyncio.run(run_smoke())


def test_tui_module_card_shows_provenance(introspector_modules) -> None:
    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.action_open_selected_module()
            await pilot.pause()
            artifact_panel = str(app.query_one("#module-artifacts").visual)
            assert "detail_source: derived" in artifact_panel
            assert "detail_variant: unknown" in artifact_panel
            assert "related_artifacts" in artifact_panel
            assert str(app.query_one("#module-artifacts").tooltip) == (
                "Provenance and freshness for the detail artifact currently shown."
            )

    asyncio.run(run_smoke())


def test_tui_module_card_flags_stale_artifact_against_scan_timestamp(introspector_modules) -> None:
    class StaleArtifactClient(FakeTuiClient):
        def __init__(self, introspector_modules) -> None:
            super().__init__(introspector_modules)
            artifact = self.analyses["project_introspector.runtime"]
            assert artifact.detail_ref is not None
            artifact.detail_ref.updated_at = "2026-04-03T23:59:00"

        def load_latest_project_scan(self, *, force: bool = False):
            return ProjectScanSummary(
                summary_path=Path("/tmp/project_scan_summary.json"),
                project_name="demo",
                source_root="/tmp/src",
                modules_scanned=3,
                scan_errors=0,
                scanned_at="2026-04-04T00:00:00+00:00",
                output_dir="/tmp/project_scan",
            )

    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=StaleArtifactClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.action_open_selected_module()
            await pilot.pause()
            artifact_panel = str(app.query_one("#module-artifacts").visual)
            assert "freshness: stale | scan_at=2026-04-04T00:00:00+00:00" in artifact_panel
            assert (
                "evidence_reason: artifact timestamp is older than scan timestamp"
                in artifact_panel
            )
            assert (
                "operator_hint: Artifact predates the scan; rerun enrichment if scan-aligned evidence is needed."
                in artifact_panel
            )

    asyncio.run(run_smoke())


def test_tui_module_card_flags_unknown_freshness_when_artifact_timestamp_missing(introspector_modules) -> None:
    class UnknownFreshnessClient(FakeTuiClient):
        def __init__(self, introspector_modules) -> None:
            super().__init__(introspector_modules)
            artifact = self.analyses["project_introspector.runtime"]
            assert artifact.detail_ref is not None
            artifact.detail_ref.updated_at = None

    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=UnknownFreshnessClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.action_open_selected_module()
            await pilot.pause()
            artifact_panel = str(app.query_one("#module-artifacts").visual)
            assert "freshness: unknown | scan_at=2026-04-04T00:00:00+00:00" in artifact_panel
            assert "evidence_reason: artifact timestamp is missing" in artifact_panel
            assert (
                "operator_hint: Check artifact metadata before comparing it with the scan timestamp."
                in artifact_panel
            )

    asyncio.run(run_smoke())


def test_tui_module_card_flags_unknown_freshness_for_malformed_timestamps(introspector_modules) -> None:
    class MalformedFreshnessClient(FakeTuiClient):
        def __init__(self, introspector_modules) -> None:
            super().__init__(introspector_modules)
            artifact = self.analyses["project_introspector.runtime"]
            assert artifact.detail_ref is not None
            artifact.detail_ref.updated_at = "not-a-date"

        def load_latest_project_scan(self, *, force: bool = False):
            return ProjectScanSummary(
                summary_path=Path("/tmp/project_scan_summary.json"),
                project_name="demo",
                source_root="/tmp/src",
                modules_scanned=3,
                scan_errors=0,
                scanned_at="also-not-a-date",
                output_dir="/tmp/project_scan",
            )

    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=MalformedFreshnessClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.action_open_selected_module()
            await pilot.pause()
            artifact_panel = str(app.query_one("#module-artifacts").visual)
            assert "detail_updated_at: not-a-date" in artifact_panel
            assert "freshness: unknown | scan_at=also-not-a-date" in artifact_panel
            assert "evidence_reason: artifact or scan timestamp is unparseable" in artifact_panel
            assert (
                "operator_hint: Check timestamp formatting in artifact metadata and scan summary."
                in artifact_panel
            )

    asyncio.run(run_smoke())


def test_tui_module_card_flags_absent_artifact_as_unknown_freshness(introspector_modules) -> None:
    class AbsentArtifactClient(FakeTuiClient):
        def __init__(self, introspector_modules) -> None:
            super().__init__(introspector_modules)
            artifact = self.analyses["project_introspector.runtime"]
            assert artifact.detail_ref is not None
            artifact.detail_ref.exists = False
            artifact.detail_ref.updated_at = "2026-04-04T00:02:00+00:00"

    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=AbsentArtifactClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.action_open_selected_module()
            await pilot.pause()
            artifact_panel = str(app.query_one("#module-artifacts").visual)
            assert "detail_updated_at: 2026-04-04T00:02:00+00:00" in artifact_panel
            assert "freshness: unknown | scan_at=2026-04-04T00:00:00+00:00" in artifact_panel
            assert "evidence_reason: artifact is absent" in artifact_panel
            assert (
                "operator_hint: Open the artifact path or rerun enrichment if the file is expected."
                in artifact_panel
            )
            assert "artifact_exists: False" in artifact_panel

    asyncio.run(run_smoke())


def test_tui_module_card_compacts_missing_analysis_empty_sections(introspector_modules) -> None:
    class NoAnalysisClient(FakeTuiClient):
        def load_derived_analyses(self, module_paths, *, storage_layout=None, force: bool = False):
            return {}

    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=NoAnalysisClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.action_open_selected_module()
            await pilot.pause()
            module_summary = str(app.query_one("#module-summary").visual)
            detail_body = str(app.query_one("#module-detail-body").visual)
            artifact_panel = str(app.query_one("#module-artifacts").visual)
            assert "semantic_output: unavailable" in module_summary
            assert "semantic module detail is unavailable because enrichment artifact is absent" in detail_body
            assert "empty semantic sections: Warnings, Actionable hints, Derivation notes, Role in system, Public symbols" in detail_body
            assert "Warnings:\n- none" not in detail_body
            assert "Derivation notes:\n- none" not in detail_body
            assert "artifact: unavailable" in artifact_panel

    asyncio.run(run_smoke())


def test_tui_module_card_flags_unknown_freshness_when_scan_timestamp_missing(
    introspector_modules,
) -> None:
    class MissingScanTimestampClient(FakeTuiClient):
        def load_latest_project_scan(self, *, force: bool = False):
            return ProjectScanSummary(
                summary_path=Path("/tmp/project_scan_summary.json"),
                project_name="demo",
                source_root="/tmp/src",
                modules_scanned=3,
                scan_errors=0,
                scanned_at=None,
                output_dir="/tmp/project_scan",
            )

    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=MissingScanTimestampClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.action_open_selected_module()
            await pilot.pause()
            artifact_panel = str(app.query_one("#module-artifacts").visual)
            assert "freshness: unknown | scan_at=unknown" in artifact_panel
            assert "evidence_reason: scan timestamp is missing" in artifact_panel
            assert (
                "operator_hint: Run or load a factual scan with scanned_at before comparing timestamps."
                in artifact_panel
            )

    asyncio.run(run_smoke())


def test_tui_module_card_flags_current_when_artifact_timestamp_matches_scan(
    introspector_modules,
) -> None:
    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.action_open_selected_module()
            await pilot.pause()
            artifact_panel = str(app.query_one("#module-artifacts").visual)
            assert "freshness: current | scan_at=2026-04-04T00:00:00+00:00" in artifact_panel
            assert (
                "evidence_reason: artifact timestamp is at or after scan timestamp"
                in artifact_panel
            )
            assert (
                "operator_hint: Artifact timestamp is not older than the scan timestamp."
                in artifact_panel
            )

    asyncio.run(run_smoke())


def test_tui_russian_module_card_localizes_labels_and_meta(introspector_modules) -> None:
    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#btn-language")
            await pilot.pause()
            await app.action_open_selected_module()
            await pilot.pause()
            module_summary = str(app.query_one("#module-summary").visual)
            detail_body = str(app.query_one("#module-detail-body").visual)
            artifact_panel = str(app.query_one("#module-artifacts").visual)

            assert "путь_модуля:" in module_summary
            assert "путь_исходника:" in module_summary
            assert "назначение:" in module_summary
            assert "статус: активен" in module_summary
            assert "обогащение: готово" in module_summary
            assert "деградация: нет" in module_summary
            assert "пустые смысловые секции: Предупреждения" in detail_body
            assert "Практические подсказки:" in detail_body
            assert "Как получен вывод:" in detail_body
            assert "Роль в системе:" in detail_body
            assert "источник_деталей: производный" in artifact_panel
            assert "вариант_деталей: неизвестно" in artifact_panel
            assert "свежесть: актуален | scan_at=2026-04-04T00:00:00+00:00" in artifact_panel
            assert "причина_evidence: timestamp артефакта не старше timestamp скана" in artifact_panel
            assert (
                "подсказка_оператору: Timestamp артефакта не старше timestamp скана."
                in artifact_panel
            )
            assert "связанные_артефакты:" in artifact_panel
            assert "источник=enrichment-replay | вариант=дешёвый" in artifact_panel

    asyncio.run(run_smoke())


def test_tui_compact_mode_updates_selected_module_from_tree(introspector_modules, monkeypatch) -> None:
    async def run_smoke() -> None:
        monkeypatch.setenv("INTROSPECTOR_TUI_COMPACT", "1")
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one("#module-tree")
            before = app.selected_module_path
            tree.root.expand_all()

            target = None
            queue = list(tree.root.children)
            while queue:
                node = queue.pop(0)
                if isinstance(node.data, str) and node.data != before:
                    target = node
                    break
                queue.extend(node.children)

            assert target is not None
            tree.select_node(target)
            await pilot.pause()

            assert app.selected_module_path == target.data
            assert f"module_path: {target.data}" in str(app.query_one("#module-summary").visual)

    asyncio.run(run_smoke())


def test_tui_compact_mode_marks_provider_actions_unavailable(introspector_modules, monkeypatch) -> None:
    async def run_smoke() -> None:
        monkeypatch.setenv("INTROSPECTOR_TUI_COMPACT", "1")
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            compact_actions = str(app.query_one("#compact-actions").visual)
            assert "Run Enrichment Queue [unavailable: provider not configured]" in compact_actions
            assert "Enrich Selected [unavailable: provider not configured]" in compact_actions

    asyncio.run(run_smoke())


def test_localize_free_text_translates_known_policy_phrases() -> None:
    assert localize_free_text("ru", "Treat this as an active path and verify changes with runtime evidence.") == (
        "Считай этот модуль активным путём и проверяй изменения по runtime-доказательствам."
    )
    assert localize_free_text("ru", "high semantic drift: public_symbols, runtime_hotspots") == (
        "сильный семантический дрейф: public_symbols, runtime_hotspots"
    )
    assert localize_free_text("ru", "Runs the radar guard cadence workflow for this module.") == (
        "Запускает workflow radar guard cadence для этого модуля."
    )


def test_tui_disables_provider_actions_when_unconfigured(introspector_modules) -> None:
    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#btn-live-pass", Button).disabled is True
            assert app.query_one("#btn-reanalyze", Button).disabled is True
            top_status = str(app.query_one("#top-status").visual)
            await app.action_trigger_live_pass()
            await pilot.pause()
            replay_status = str(app.query_one("#replay-status").visual)
            replay_actions = str(app.query_one("#replay-actions").visual)
            assert app.query_one("#btn-scan-project", Button).disabled is False
            assert "scan=schema_loaded" in top_status
            assert "analysis source=unconfigured" in top_status
            assert "provider_actions: unavailable" in replay_status
            assert "operator_next: review enriched module evidence and freshness" in replay_status
            assert "provider_configured" not in replay_status
            assert "provider_action_reason: provider is not configured; factual scan remains available" in replay_status
            assert (
                "operator_hint: run factual scan only or configure provider before enrichment"
                in replay_status
            )
            assert (
                "provider-backed action unavailable: provider is not configured; factual scan remains available"
                in replay_actions
            )
            assert str(app.query_one("#btn-live-pass", Button).tooltip) == (
                "Requires confirmation. Run provider-backed enrichment for the baseline queue modules without re-running factual scan.\n"
                "Unavailable: provider is not configured; factual scan remains available."
            )
            assert str(app.query_one("#btn-reanalyze", Button).tooltip) == (
                "Requires confirmation. Run provider-backed enrichment for the currently selected module.\n"
                "Unavailable: provider is not configured; factual scan remains available."
            )
            assert str(app.query_one("#btn-scan-project", Button).tooltip) == (
                "Requires confirmation. Re-run the non-LLM static scan and upload a fresh schema snapshot."
            )

    asyncio.run(run_smoke())


def test_tui_shows_provider_actions_available_when_configured(introspector_modules) -> None:
    class ConfiguredClient(FakeTuiClient):
        def __init__(self, introspector_modules) -> None:
            super().__init__(introspector_modules)
            self.status.configured = True

    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=ConfiguredClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#btn-live-pass", Button).disabled is False
            assert app.query_one("#btn-reanalyze", Button).disabled is False
            top_status = str(app.query_one("#top-status").visual)
            replay_status = str(app.query_one("#replay-status").visual)
            assert "scan=schema_loaded" in top_status
            assert "analysis source=configured" in top_status
            assert "provider_actions: available" in replay_status
            assert "operator_next: review enriched module evidence and freshness" in replay_status
            assert "provider_action_reason: provider is configured" in replay_status
            assert "operator_hint: enrichment actions can run; verify factual scan first" in replay_status
            assert str(app.query_one("#btn-live-pass", Button).tooltip) == (
                "Requires confirmation. Run provider-backed enrichment for the baseline queue modules without re-running factual scan."
            )
            assert str(app.query_one("#btn-reanalyze", Button).tooltip) == (
                "Requires confirmation. Run provider-backed enrichment for the currently selected module."
            )

    asyncio.run(run_smoke())


def test_tui_russian_provider_action_availability_text(introspector_modules) -> None:
    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#btn-language")
            await pilot.pause()
            top_status = str(app.query_one("#top-status").visual)
            replay_status = str(app.query_one("#replay-status").visual)
            live_pass_tooltip = str(app.query_one("#btn-live-pass", Button).tooltip)
            assert "скан=schema_loaded" in top_status
            assert "источник анализа=unconfigured" in top_status
            assert "provider_actions: недоступны" in replay_status
            assert "следующий_шаг: проверь evidence и свежесть обогащённых модулей" in replay_status
            assert "provider_configured" not in replay_status
            assert "причина_доступности_enrichment: provider не настроен; factual scan остаётся доступен" in replay_status
            assert (
                "следующий_шаг: запускай только factual scan или настрой provider перед enrichment"
                in replay_status
            )
            assert str(app.query_one("#btn-live-pass", Button).tooltip) == (
                "Требует подтверждения. Запускает provider-backed enrichment для очереди модулей без повторного factual scan.\n"
                "Недоступно: provider не настроен; factual scan остаётся доступен."
            )
            assert "Недоступно: provider не настроен; factual scan остаётся доступен." in live_pass_tooltip

    asyncio.run(run_smoke())


def test_tui_baseline_modules_expose_expected_fields(introspector_modules) -> None:
    expected_modules = [
        "project_introspector.runtime",
        "project_introspector.tui_client",
        "project_introspector.tui_app",
    ]

    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            for module_path in expected_modules:
                app.selected_module_path = module_path
                await app.action_open_selected_module()
                await pilot.pause()
                module_summary = str(app.query_one("#module-summary").visual)
                detail_body = str(app.query_one("#module-detail-body").visual)
                artifacts = str(app.query_one("#module-artifacts").visual)

                assert f"module_path: {module_path}" in module_summary
                assert "purpose:" in module_summary
                assert "status:" in module_summary
                assert "enrichment:" in module_summary
                assert "degraded:" in module_summary
                assert "Warnings:" in detail_body or "empty semantic sections: Warnings" in detail_body
                assert "Actionable hints:" in detail_body
                assert "Derivation notes:" in detail_body
                assert "Role in system:" in detail_body
                assert "Public symbols:" in detail_body
                assert "Processing notes:" not in detail_body
                assert "Responsibilities:" not in detail_body
                assert detail_body.index("Actionable hints:") < detail_body.index("Derivation notes:")
                assert detail_body.index("Derivation notes:") < detail_body.index("Role in system:")
                assert detail_body.index("Role in system:") < detail_body.index("Public symbols:")
                assert "detail_source:" in artifacts
                assert "detail_variant:" in artifacts
                assert "detail_updated_at:" in artifacts

    asyncio.run(run_smoke())


def test_tui_live_pass_refreshes_module_views_without_schema_reload(introspector_modules) -> None:
    class LivePassClient(FakeTuiClient):
        def __init__(self, introspector_modules) -> None:
            super().__init__(introspector_modules)
            self.status.configured = True
            self.live_pass_runs = 0

        def run_live_pass(self):
            self.live_pass_runs += 1
            return type("Result", (), {"returncode": 0, "stdout": "live pass done", "stderr": "", "timed_out": False})()

        def load_derived_analyses(self, module_paths, *, storage_layout=None, force: bool = False):
            if force and self.live_pass_runs:
                updated = {}
                for module_path in module_paths:
                    artifact = self.analyses[module_path]
                    updated[module_path] = ModuleAnalysisArtifact(
                        analysis=LLMModuleAnalysis(
                            module_path=module_path,
                            purpose=f"updated after live pass: {module_path}",
                            responsibilities=artifact.analysis.responsibilities if artifact.analysis else [],
                            public_symbols=artifact.analysis.public_symbols if artifact.analysis else [],
                            status=artifact.analysis.status if artifact.analysis else "active",
                            actionable_hints=artifact.analysis.actionable_hints if artifact.analysis else [],
                            warnings=artifact.analysis.warnings if artifact.analysis else [],
                            processing_notes=artifact.analysis.processing_notes if artifact.analysis else [],
                            degraded=artifact.analysis.degraded if artifact.analysis else False,
                        ),
                        artifact_path=artifact.artifact_path,
                        detail_ref=artifact.detail_ref,
                        related_refs=artifact.related_refs,
                    )
                return updated
            return super().load_derived_analyses(module_paths, storage_layout=storage_layout, force=force)

    async def run_smoke() -> None:
        client = LivePassClient(introspector_modules)
        app = IntrospectorTuiApp(client=client)
        async with app.run_test() as pilot:
            await pilot.pause()
            schema_calls_before = client.fetch_schema_calls
            await app.action_trigger_live_pass()
            await pilot.pause()
            assert client.live_pass_runs == 0
            assert "Confirm:" in str(app.query_one("#btn-live-pass", Button).label)
            await app.action_trigger_live_pass()
            await pilot.pause()
            await app.action_open_selected_module()
            await pilot.pause()
            assert client.fetch_schema_calls == schema_calls_before
            assert "updated after live pass" in str(app.query_one("#module-summary").visual)

    asyncio.run(run_smoke())


def test_tui_scan_project_runs_non_llm_refresh(introspector_modules) -> None:
    async def run_smoke() -> None:
        client = FakeTuiClient(introspector_modules)
        app = IntrospectorTuiApp(client=client)
        async with app.run_test() as pilot:
            await pilot.pause()
            calls_before = client.fetch_schema_calls
            await app.action_scan_project()
            await pilot.pause()
            assert client.project_scan_runs == 0
            assert "Confirm:" in str(app.query_one("#btn-scan-project", Button).label)
            await pilot.press("escape")
            await pilot.pause()
            assert client.project_scan_runs == 0
            assert str(app.query_one("#btn-scan-project", Button).label) == "Scan Project"
            assert "Confirmation cancelled" in str(app.query_one("#top-status").visual)
            await app.action_scan_project()
            await pilot.pause()
            await app.action_scan_project()
            await pilot.pause()
            assert client.project_scan_runs == 1
            assert client.fetch_schema_calls > calls_before
            replay_last_pass = str(app.query_one("#replay-last-pass").visual)
            assert "source_root: /tmp/src" in replay_last_pass

    asyncio.run(run_smoke())


def test_tui_shows_error_state_when_analyzer_is_unreachable(introspector_modules) -> None:
    class OfflineClient(FakeTuiClient):
        def fetch_status(self, *, force: bool = False):
            request = httpx.Request("GET", "http://127.0.0.1:8015/llm/status")
            raise httpx.ConnectError("connection refused", request=request)

    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=OfflineClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            top_status = str(app.query_one("#top-status").visual)
            replay_status = str(app.query_one("#replay-status").visual)
            replay_storage = str(app.query_one("#replay-storage").visual)
            assert "ConnectError" in top_status
            assert "ConnectError" in replay_status or "unavailable" in replay_storage

    asyncio.run(run_smoke())


def test_mouse_is_enabled_by_default_inside_tmux(monkeypatch) -> None:
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1,0")
    monkeypatch.delenv("INTROSPECTOR_TUI_MOUSE", raising=False)

    assert _mouse_enabled_from_env() is True


def test_mouse_can_be_forced_off_inside_tmux(monkeypatch) -> None:
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1,0")
    monkeypatch.setenv("INTROSPECTOR_TUI_MOUSE", "0")

    assert _mouse_enabled_from_env() is False


def test_tab_does_not_mutate_screen_layout(introspector_modules) -> None:
    async def run_smoke() -> None:
        app = IntrospectorTuiApp(client=FakeTuiClient(introspector_modules))
        async with app.run_test() as pilot:
            await pilot.pause()
            before = str(app.query_one("#main-tabs").active), str(app.query_one("#module-summary").visual)
            await pilot.press("tab")
            await pilot.pause()
            after = str(app.query_one("#main-tabs").active), str(app.query_one("#module-summary").visual)
            assert after == before

    asyncio.run(run_smoke())



def test_localize_semantic_text_falls_back_to_generic_translation_without_qiki_codes() -> None:
    assert localize_semantic_text(
        'ru',
        'Process module-specific inputs into structured results.',
        code='resp.generic.process_inputs',
        kind='responsibility',
    ) == 'Обрабатывает входы, специфичные для модуля, в структурированные результаты.'


def test_localize_semantic_text_falls_back_to_original_text_for_unknown_codes() -> None:
    assert localize_semantic_text(
        'ru',
        'Coordinate one workflow step across declared module components.',
        code='purpose.unknown.workflow_step',
        kind='purpose',
    ) == 'Coordinate one workflow step across declared module components.'
    assert localize_semantic_text(
        'ru',
        'Assemble structured reports for downstream consumers.',
        code='resp.unknown.assemble_reports',
        kind='responsibility',
    ) == 'Assemble structured reports for downstream consumers.'
