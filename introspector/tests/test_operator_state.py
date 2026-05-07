from __future__ import annotations

import json
from pathlib import Path

from project_introspector.models import CodeLocation, FastAPIRouteFact, LLMModuleAnalysis, ModuleFact, ProjectSchema
from project_introspector.operator_state import build_operator_state
from project_introspector.run_contract import (
    ArtifactKind,
    IssueSeverity,
    LayerStatus,
    RunArtifactRef,
    RunFactualLayer,
    RunIssue,
    RunMode,
    RunNextStep,
    RunReportLayer,
    RunResult,
    RunStatus,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_operator_state_builds_dashboard_model_from_run_directory(tmp_path: Path) -> None:
    location = CodeLocation(file_path="src/pkg/api.py", module_path="pkg.api", lineno=1)
    module = ModuleFact(
        module_path="pkg.api",
        file_path="src/pkg/api.py",
        file_hash="hash",
        fastapi_routes=[FastAPIRouteFact(method="GET", path="/health", qualified_name="pkg.api.health", decorator='app.get("/health")', app_name="app", location=location)],
    )
    schema = ProjectSchema(
        project_name="demo",
        module_count=1,
        function_count=0,
        class_count=0,
        runtime_event_count=0,
        modules=[module],
        edges=[],
        symbols=[],
    )
    result = RunResult(
        run_id="run-1",
        project_name="demo",
        source_root="src",
        mode=RunMode.OFFLINE,
        status=RunStatus.COMPLETED_WITH_LIMITS,
        started_at="2026-05-03T00:00:00Z",
        factual_layer=RunFactualLayer(status=LayerStatus.READY, modules_scanned=1, snapshot_path="static_snapshot.json", schema_path="schema.json"),
        report_layer=RunReportLayer(status=LayerStatus.SKIPPED),
        artifacts=[
            RunArtifactRef(kind=ArtifactKind.STATIC_SNAPSHOT, path="static_snapshot.json", required=True),
            RunArtifactRef(kind=ArtifactKind.SCHEMA, path="schema.json", required=True),
        ],
        limits=[RunIssue(code="runtime_absent", severity=IssueSeverity.WARNING, message="No runtime events")],
        next_safe_steps=[RunNextStep(code="review_report", message="Review generated artifacts")],
    )
    _write(tmp_path / "run_result.json", result)
    _write(tmp_path / "schema.json", schema)
    _write(tmp_path / "static_snapshot.json", {"ok": True})

    state = build_operator_state(tmp_path)

    assert state.run.run_id == "run-1"
    assert state.run.status == "completed_with_limits"
    assert {layer.name: layer.status for layer in state.layers}["factual"] == "ready"
    assert state.artifacts[0].exists is True
    assert state.modules[0].module_path == "pkg.api"
    assert state.modules[0].route_count == 1
    assert state.warnings == ["runtime_absent"]
    assert state.next_safe_steps == ["Review generated artifacts"]


def test_operator_state_discovers_latest_run_directory(tmp_path: Path) -> None:
    from project_introspector.operator_state import discover_latest_run_dir, discover_run_directories

    older = tmp_path / "20260503T010000Z_demo"
    newer = tmp_path / "20260503T020000Z_demo"
    older.mkdir()
    newer.mkdir()
    (older / "run_result.json").write_text("{}", encoding="utf-8")
    (newer / "run_result.json").write_text("{}", encoding="utf-8")

    discovered = discover_run_directories(tmp_path)

    assert discovered[0] == newer
    assert discover_latest_run_dir(tmp_path) == newer


def test_operator_state_from_analyzer_payloads_counts_live_inputs(tmp_path: Path) -> None:
    from project_introspector.operator_state import build_operator_state_from_analyzer_payloads

    location = CodeLocation(file_path="src/pkg/api.py", module_path="pkg.api", lineno=1)
    module = ModuleFact(
        module_path="pkg.api",
        file_path="src/pkg/api.py",
        file_hash="hash",
        fastapi_routes=[FastAPIRouteFact(method="GET", path="/health", qualified_name="pkg.api.health", decorator='app.get("/health")', app_name="app", location=location)],
    )
    schema = ProjectSchema(
        project_name="demo",
        module_count=1,
        function_count=0,
        class_count=0,
        runtime_event_count=0,
        modules=[module],
        edges=[],
        symbols=[],
    )
    analysis = LLMModuleAnalysis(module_path="pkg.api", purpose="api", status="active", degraded=True)
    artifact = type("Artifact", (), {"analysis": analysis})()

    state = build_operator_state_from_analyzer_payloads(
        project_name="demo",
        schema=schema,
        report={"limits": [{"code": "runtime_absent"}], "next_safe_steps": ["Review report"]},
        llm_status={"configured": True, "probe_status": "not_checked"},
        scan_summary={"source_root": "src", "modules_scanned": 1},
        live_pass_summary={"enrichment_status": "done"},
        analyses={"pkg.api": artifact},
    )

    assert state.run.run_id == "analyzer-live"
    assert state.layers[0].status == "ready"
    assert state.modules[0].route_count == 1
    assert state.modules[0].enriched is True
    assert state.modules[0].degraded is True
    assert state.warnings == ["runtime_absent"]
    assert state.next_safe_steps == ["Review report"]
