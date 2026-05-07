from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from .run_contract import IssueSeverity, LayerStatus, RunIssue, RunResult, RunStatus


class RunValidationFinding(BaseModel):
    code: str
    severity: IssueSeverity
    message: str
    path: str | None = None
    layer: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class RunValidationReport(BaseModel):
    ok: bool
    findings: list[RunValidationFinding] = Field(default_factory=list)

    def has_errors(self) -> bool:
        return any(finding.severity == IssueSeverity.ERROR for finding in self.findings)


def _finding(code: str, severity: IssueSeverity, message: str, **kwargs: Any) -> RunValidationFinding:
    return RunValidationFinding(code=code, severity=severity, message=message, **kwargs)


def load_run_result(run_dir: Path) -> RunResult:
    path = run_dir / 'run_result.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    return RunResult.model_validate(data)


def _has_issue(result: RunResult, code: str) -> bool:
    return any(issue.code == code for issue in result.limits)


def validate_run_result(run_dir: Path, result: RunResult) -> RunValidationReport:
    findings: list[RunValidationFinding] = []
    for artifact in result.artifacts:
        path = run_dir / artifact.path
        if artifact.required and not path.exists():
            findings.append(_finding('required_artifact_missing', IssueSeverity.ERROR, f'Required artifact is missing: {artifact.path}', path=artifact.path))
        elif not artifact.required and artifact.path and not path.exists():
            findings.append(_finding('declared_artifact_missing', IssueSeverity.WARNING, f'Declared optional artifact is missing: {artifact.path}', path=artifact.path))

    factual = result.factual_layer
    if factual.status == LayerStatus.READY and not factual.snapshot_path:
        findings.append(_finding('factual_ready_without_snapshot', IssueSeverity.ERROR, 'factual_layer.status=ready but snapshot_path is missing.', layer='factual'))
    if factual.snapshot_path and not (run_dir / factual.snapshot_path).exists():
        findings.append(_finding('snapshot_missing', IssueSeverity.ERROR, f'Static snapshot is missing: {factual.snapshot_path}', path=factual.snapshot_path, layer='factual'))
    if factual.schema_path and not (run_dir / factual.schema_path).exists():
        findings.append(_finding('schema_missing', IssueSeverity.ERROR, f'Schema file is missing: {factual.schema_path}', path=factual.schema_path, layer='factual'))
    if factual.status == LayerStatus.FAILED and result.status == RunStatus.COMPLETED:
        findings.append(_finding('factual_failed_but_run_completed', IssueSeverity.ERROR, 'factual layer failed but run status is completed.', layer='factual'))
    if factual.scan_errors > 0 and result.status == RunStatus.COMPLETED and not _has_issue(result, 'scan_errors_present'):
        findings.append(_finding('scan_errors_missing_issue', IssueSeverity.WARNING, 'scan_errors > 0 should be reflected in limits.', layer='factual'))

    runtime = result.runtime_layer
    if runtime.status == LayerStatus.READY and runtime.runtime_event_count <= 0:
        findings.append(_finding('runtime_ready_without_events', IssueSeverity.WARNING, 'runtime_layer.status=ready but runtime_event_count is 0.', layer='runtime'))
    if runtime.runtime_event_count == 0 and runtime.status != LayerStatus.ABSENT:
        findings.append(_finding('runtime_zero_not_absent', IssueSeverity.WARNING, 'runtime_event_count=0 should normally mean runtime_layer.status=absent.', layer='runtime'))
    if runtime.runtime_event_count == 0 and not _has_issue(result, 'runtime_absent'):
        findings.append(_finding('runtime_absent_missing_limit', IssueSeverity.WARNING, 'No runtime events are present; run limits should mention runtime_absent.', layer='runtime'))

    enrichment = result.enrichment_layer
    if enrichment.status == LayerStatus.READY and not enrichment.provider_configured:
        findings.append(_finding('enrichment_ready_without_provider', IssueSeverity.ERROR, 'enrichment is ready but provider_configured=false.', layer='enrichment'))
    if enrichment.module_findings_dir and not (run_dir / enrichment.module_findings_dir).exists():
        severity = IssueSeverity.ERROR if enrichment.status == LayerStatus.READY else IssueSeverity.WARNING
        findings.append(_finding('module_findings_dir_missing', severity, f'module_findings_dir is missing: {enrichment.module_findings_dir}', path=enrichment.module_findings_dir, layer='enrichment'))

    report = result.report_layer
    if report.status == LayerStatus.READY:
        if not report.report_path:
            findings.append(_finding('report_ready_without_path', IssueSeverity.ERROR, 'report_layer.status=ready but report_path is missing.', layer='report'))
        elif not (run_dir / report.report_path).exists():
            findings.append(_finding('report_missing', IssueSeverity.ERROR, f'report.json is missing: {report.report_path}', path=report.report_path, layer='report'))
        else:
            try:
                parsed = json.loads((run_dir / report.report_path).read_text(encoding='utf-8'))
                if not isinstance(parsed, dict):
                    raise ValueError('report is not an object')
            except Exception:
                findings.append(_finding('report_invalid_json', IssueSeverity.ERROR, 'report file is not a valid JSON object.', path=report.report_path, layer='report'))

    if any(item.severity == IssueSeverity.ERROR for item in findings) and result.status == RunStatus.COMPLETED:
        findings.append(_finding('top_status_too_optimistic', IssueSeverity.ERROR, 'run status cannot be completed while validation errors exist.'))

    return RunValidationReport(ok=not any(item.severity == IssueSeverity.ERROR for item in findings), findings=findings)


def validate_run_directory(run_dir: Path) -> RunValidationReport:
    path = run_dir / 'run_result.json'
    if not path.exists():
        return RunValidationReport(ok=False, findings=[_finding('run_result_missing', IssueSeverity.ERROR, 'run_result.json is missing.')])
    try:
        result = load_run_result(run_dir)
    except json.JSONDecodeError as exc:
        return RunValidationReport(ok=False, findings=[_finding('run_result_invalid_json', IssueSeverity.ERROR, f'run_result.json is invalid JSON: {exc}')])
    except ValidationError as exc:
        return RunValidationReport(ok=False, findings=[_finding('run_result_schema_invalid', IssueSeverity.ERROR, f'run_result.json does not match RunResult: {exc}')])
    return validate_run_result(run_dir, result)


def normalize_run_result(run_dir: Path, result: RunResult, validation: RunValidationReport) -> RunResult:
    existing_codes = {issue.code for issue in result.limits}
    for finding in validation.findings:
        if finding.code in existing_codes:
            continue
        result.limits.append(
            RunIssue(
                code=finding.code,
                severity=finding.severity,
                message=finding.message,
                layer=finding.layer,
                details=finding.details,
            )
        )
        existing_codes.add(finding.code)
    if validation.has_errors():
        result.status = RunStatus.FAILED if result.factual_layer.status == LayerStatus.FAILED else RunStatus.DEGRADED
    elif validation.findings and result.status == RunStatus.COMPLETED:
        result.status = RunStatus.COMPLETED_WITH_LIMITS
    return result
