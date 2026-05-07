from __future__ import annotations

import json
from pathlib import Path

from project_introspector.run_contract import (
    ArtifactKind,
    LayerStatus,
    RunArtifactRef,
    RunEnrichmentLayer,
    RunFactualLayer,
    RunMode,
    RunReportLayer,
    RunResult,
    RunStatus,
)
from project_introspector.run_validator import validate_run_directory


def _write_result(run_dir: Path, result: RunResult) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_result.json").write_text(json.dumps(result.model_dump(mode="json")), encoding="utf-8")


def _base_result(**overrides) -> RunResult:
    data = dict(
        run_id="demo-run",
        project_name="demo",
        source_root="src",
        mode=RunMode.OFFLINE,
        status=RunStatus.COMPLETED_WITH_LIMITS,
        started_at="2026-05-03T00:00:00Z",
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
        ],
    )
    data.update(overrides)
    return RunResult(**data)


def test_validator_errors_when_static_snapshot_required_but_missing(tmp_path: Path) -> None:
    (tmp_path / "summary.json").write_text("{}", encoding="utf-8")
    (tmp_path / "schema.json").write_text("{}", encoding="utf-8")
    _write_result(tmp_path, _base_result(status=RunStatus.COMPLETED))

    report = validate_run_directory(tmp_path)

    assert report.ok is False
    codes = {finding.code for finding in report.findings}
    assert "required_artifact_missing" in codes
    assert "snapshot_missing" in codes
    assert "top_status_too_optimistic" in codes


def test_validator_errors_when_report_ready_but_report_missing(tmp_path: Path) -> None:
    for name in ["static_snapshot.json", "summary.json", "schema.json"]:
        (tmp_path / name).write_text("{}", encoding="utf-8")
    _write_result(
        tmp_path,
        _base_result(
            mode=RunMode.ANALYZER_BACKED,
            status=RunStatus.COMPLETED,
            report_layer=RunReportLayer(status=LayerStatus.READY, report_path="report.json"),
            artifacts=[
                RunArtifactRef(kind=ArtifactKind.STATIC_SNAPSHOT, path="static_snapshot.json", required=True),
                RunArtifactRef(kind=ArtifactKind.SCAN_SUMMARY, path="summary.json", required=True),
                RunArtifactRef(kind=ArtifactKind.SCHEMA, path="schema.json", required=True),
                RunArtifactRef(kind=ArtifactKind.REPORT, path="report.json", required=True),
            ],
        ),
    )

    report = validate_run_directory(tmp_path)

    assert report.ok is False
    codes = {finding.code for finding in report.findings}
    assert "report_missing" in codes
    assert "required_artifact_missing" in codes


def test_validator_errors_when_schema_path_declared_but_file_missing(tmp_path: Path) -> None:
    for name in ["static_snapshot.json", "summary.json"]:
        (tmp_path / name).write_text("{}", encoding="utf-8")
    _write_result(
        tmp_path,
        _base_result(
            artifacts=[
                RunArtifactRef(kind=ArtifactKind.STATIC_SNAPSHOT, path="static_snapshot.json", required=True),
                RunArtifactRef(kind=ArtifactKind.SCAN_SUMMARY, path="summary.json", required=True),
            ],
        ),
    )

    report = validate_run_directory(tmp_path)

    assert report.ok is False
    assert any(finding.code == "schema_missing" for finding in report.findings)


def test_validator_errors_when_ready_enrichment_module_dir_missing(tmp_path: Path) -> None:
    for name in ["static_snapshot.json", "summary.json", "schema.json"]:
        (tmp_path / name).write_text("{}", encoding="utf-8")
    _write_result(
        tmp_path,
        _base_result(
            mode=RunMode.FULL,
            enrichment_layer=RunEnrichmentLayer(
                status=LayerStatus.READY,
                provider_configured=True,
                module_findings_dir="module_findings",
            ),
        ),
    )

    report = validate_run_directory(tmp_path)

    assert report.ok is False
    assert any(finding.code == "module_findings_dir_missing" and finding.severity.value == "error" for finding in report.findings)


def test_offline_run_does_not_require_report_artifact(tmp_path: Path) -> None:
    for name in ["static_snapshot.json", "summary.json", "schema.json"]:
        (tmp_path / name).write_text("{}", encoding="utf-8")
    _write_result(tmp_path, _base_result())

    report = validate_run_directory(tmp_path)

    assert report.ok is True
    assert not any(finding.code == "report_missing" for finding in report.findings)
