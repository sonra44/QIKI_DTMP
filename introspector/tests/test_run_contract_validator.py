from __future__ import annotations

import json
from pathlib import Path

from project_introspector.run_contract import (
    ArtifactKind,
    LayerStatus,
    RunArtifactRef,
    RunFactualLayer,
    RunMode,
    RunReportLayer,
    RunResult,
    RunStatus,
)
from project_introspector.run_validator import validate_run_directory


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_run_validator_accepts_minimal_offline_run(tmp_path: Path) -> None:
    for name in ["static_snapshot.json", "summary.json", "schema.json"]:
        _write(tmp_path / name, {})
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "progress.log").write_text("ok\n", encoding="utf-8")

    result = RunResult(
        run_id="demo-run",
        project_name="demo",
        source_root="src",
        mode=RunMode.OFFLINE,
        status=RunStatus.COMPLETED_WITH_LIMITS,
        started_at="2026-05-02T00:00:00Z",
        completed_at="2026-05-02T00:00:01Z",
        factual_layer=RunFactualLayer(
            status=LayerStatus.READY,
            modules_scanned=1,
            scan_errors=0,
            snapshot_path="static_snapshot.json",
            schema_path="schema.json",
        ),
        report_layer=RunReportLayer(status=LayerStatus.SKIPPED),
        artifacts=[
            RunArtifactRef(kind=ArtifactKind.STATIC_SNAPSHOT, path="static_snapshot.json", required=True),
            RunArtifactRef(kind=ArtifactKind.SCAN_SUMMARY, path="summary.json", required=True),
            RunArtifactRef(kind=ArtifactKind.SCHEMA, path="schema.json", required=True),
            RunArtifactRef(kind=ArtifactKind.PROGRESS_LOG, path="logs/progress.log", required=True),
        ],
    )
    _write(tmp_path / "run_result.json", result.model_dump(mode="json"))

    report = validate_run_directory(tmp_path)

    assert report.ok is True


def test_run_validator_reports_missing_required_artifact(tmp_path: Path) -> None:
    result = RunResult(
        run_id="demo-run",
        project_name="demo",
        source_root="src",
        mode=RunMode.OFFLINE,
        status=RunStatus.COMPLETED,
        started_at="2026-05-02T00:00:00Z",
        factual_layer=RunFactualLayer(status=LayerStatus.READY, snapshot_path="static_snapshot.json"),
        report_layer=RunReportLayer(status=LayerStatus.SKIPPED),
        artifacts=[RunArtifactRef(kind=ArtifactKind.STATIC_SNAPSHOT, path="static_snapshot.json", required=True)],
    )
    _write(tmp_path / "run_result.json", result.model_dump(mode="json"))

    report = validate_run_directory(tmp_path)

    assert report.ok is False
    assert any(item.code == "required_artifact_missing" for item in report.findings)
