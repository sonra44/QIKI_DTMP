from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .artifact_freshness import ArtifactFreshness, evaluate_path_freshness
from .models import ProjectSchema
from .run_contract import RunResult


@dataclass(frozen=True, slots=True)
class OperatorLayerSummary:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OperatorArtifactSummary:
    kind: str
    path: str
    required: bool
    exists: bool
    freshness: ArtifactFreshness | None = None


@dataclass(frozen=True, slots=True)
class OperatorModuleRow:
    module_path: str
    file_path: str
    route_count: int = 0
    env_var_count: int = 0
    cli_option_count: int = 0
    pydantic_model_count: int = 0
    class_attribute_count: int = 0
    enriched: bool = False
    degraded: bool = False
    findings_count: int = 0


@dataclass(frozen=True, slots=True)
class OperatorRunSummary:
    run_id: str
    project_name: str
    mode: str
    status: str
    source_root: str


@dataclass(frozen=True, slots=True)
class OperatorState:
    run: OperatorRunSummary
    layers: list[OperatorLayerSummary]
    artifacts: list[OperatorArtifactSummary]
    modules: list[OperatorModuleRow]
    warnings: list[str]
    next_safe_steps: list[str]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def discover_run_directories(runs_root: Path) -> list[Path]:
    if not runs_root.exists():
        return []
    return sorted(
        [path for path in runs_root.iterdir() if path.is_dir() and (path / "run_result.json").exists()],
        key=lambda path: ((path / "run_result.json").stat().st_mtime_ns, path.name),
        reverse=True,
    )


def discover_latest_run_dir(runs_root: Path) -> Path | None:
    candidates = discover_run_directories(runs_root)
    return candidates[0] if candidates else None


def _schema_from_run(run_dir: Path, result: RunResult) -> ProjectSchema | None:
    schema_path = result.factual_layer.schema_path
    if not schema_path:
        return None
    path = run_dir / schema_path
    if not path.exists():
        return None
    try:
        return ProjectSchema.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _module_findings(run_dir: Path, result: RunResult) -> dict[str, dict[str, Any]]:
    findings_dir = result.enrichment_layer.module_findings_dir
    if not findings_dir:
        return {}
    root = run_dir / findings_dir
    if not root.exists():
        return {}
    findings: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        payload = _load_json(path)
        module_path = str(payload.get("module_path") or path.stem.replace("__", "."))
        findings[module_path] = payload
    return findings


def _module_rows_from_schema(
    schema: ProjectSchema | None,
    findings: Mapping[str, Mapping[str, Any]] | None = None,
    analyses: Mapping[str, Any] | None = None,
) -> list[OperatorModuleRow]:
    if schema is None:
        return []
    findings = findings or {}
    analyses = analyses or {}
    rows: list[OperatorModuleRow] = []
    for module in sorted(schema.modules, key=lambda item: item.module_path):
        finding = _as_mapping(findings.get(module.module_path))
        artifact = analyses.get(module.module_path)
        analysis = getattr(artifact, "analysis", None)
        enriched = bool(finding) or analysis is not None
        degraded = bool(finding.get("degraded")) or bool(getattr(analysis, "degraded", False))
        finding_count = sum(
            1
            for key in ("warnings", "risks", "actionable_hints", "processing_notes")
            if finding.get(key) or getattr(analysis, key, None)
        )
        rows.append(
            OperatorModuleRow(
                module_path=module.module_path,
                file_path=module.file_path,
                route_count=len(module.fastapi_routes),
                env_var_count=len(module.env_vars),
                cli_option_count=len(module.cli_options),
                pydantic_model_count=len(module.pydantic_models),
                class_attribute_count=len(module.class_attributes),
                enriched=enriched,
                degraded=degraded,
                findings_count=finding_count,
            )
        )
    return rows


def build_operator_state_from_analyzer_payloads(
    *,
    project_name: str,
    schema: ProjectSchema | None,
    report: Mapping[str, Any] | None = None,
    llm_status: Mapping[str, Any] | None = None,
    scan_summary: Mapping[str, Any] | None = None,
    live_pass_summary: Mapping[str, Any] | None = None,
    analyses: Mapping[str, Any] | None = None,
) -> OperatorState:
    report = _as_mapping(report)
    llm_status = _as_mapping(llm_status)
    scan_summary = _as_mapping(scan_summary)
    live_pass_summary = _as_mapping(live_pass_summary)
    factual_report = _as_mapping(report.get("factual_layer"))
    runtime_report = _as_mapping(report.get("runtime_layer"))
    enrichment_report = _as_mapping(report.get("enrichment_layer"))
    report_scope = _as_mapping(report.get("scope"))
    report_findings = report.get("module_findings")
    findings: dict[str, Mapping[str, Any]] = {}
    if isinstance(report_findings, list):
        for item in report_findings:
            mapping = _as_mapping(item)
            module_path = str(mapping.get("module_path") or "").strip()
            if module_path:
                findings[module_path] = mapping

    module_count = schema.module_count if schema is not None else _safe_int(factual_report.get("module_count"))
    runtime_event_count = schema.runtime_event_count if schema is not None else _safe_int(runtime_report.get("runtime_event_count"))
    modules_done = sum(1 for artifact in (analyses or {}).values() if getattr(artifact, "analysis", None) is not None)
    modules_degraded = sum(
        1
        for artifact in (analyses or {}).values()
        if getattr(getattr(artifact, "analysis", None), "degraded", False)
    )
    provider_configured = bool(llm_status.get("configured", enrichment_report.get("provider_configured", False)))
    run_summary = OperatorRunSummary(
        run_id=str(report.get("run_id") or "analyzer-live"),
        project_name=project_name,
        mode="analyzer_backed",
        status="ready" if schema is not None or report else "partial",
        source_root=str(scan_summary.get("source_root") or report_scope.get("source_root") or ""),
    )
    layers = [
        OperatorLayerSummary(
            name="factual",
            status=str(factual_report.get("status") or ("ready" if schema is not None else "absent")),
            details={
                "modules_scanned": _safe_int(scan_summary.get("modules_scanned")) or _safe_int(factual_report.get("modules_scanned")) or module_count,
                "scan_errors": _safe_int(scan_summary.get("scan_errors")) or _safe_int(factual_report.get("scan_errors")),
                "schema_ready": schema is not None,
            },
        ),
        OperatorLayerSummary(
            name="runtime",
            status=str(runtime_report.get("status") or ("present" if runtime_event_count else "absent")),
            details={"runtime_event_count": runtime_event_count},
        ),
        OperatorLayerSummary(
            name="enrichment",
            status=str(enrichment_report.get("status") or ("ready" if modules_done else "skipped")),
            details={
                "provider_configured": provider_configured,
                "provider_probe_status": llm_status.get("probe_status") or llm_status.get("provider_probe_status"),
                "modules_done": _safe_int(enrichment_report.get("modules_done")) or modules_done,
                "degraded_count": _safe_int(enrichment_report.get("modules_degraded")) or modules_degraded,
                "queue_status": live_pass_summary.get("enrichment_status"),
            },
        ),
        OperatorLayerSummary(
            name="report",
            status="ready" if report else "absent",
            details={"report_version": report.get("report_version")},
        ),
    ]
    warning_codes = [str(item.get("code")) for item in report.get("limits", []) if isinstance(item, Mapping) and item.get("code")]
    next_steps = [str(item) for item in report.get("next_safe_steps", []) if item]
    if not next_steps and not provider_configured:
        next_steps = ["Run factual scan or configure provider before enrichment."]
    return OperatorState(
        run=run_summary,
        layers=layers,
        artifacts=[],
        modules=_module_rows_from_schema(schema, findings, analyses),
        warnings=warning_codes,
        next_safe_steps=next_steps,
    )


def build_operator_state(run_dir: Path) -> OperatorState:
    result = RunResult.model_validate_json((run_dir / "run_result.json").read_text(encoding="utf-8"))
    schema = _schema_from_run(run_dir, result)
    report = _load_json(run_dir / (result.report_layer.report_path or "report.json"))
    findings = _module_findings(run_dir, result)

    run_summary = OperatorRunSummary(
        run_id=result.run_id,
        project_name=result.project_name,
        mode=result.mode.value,
        status=result.status.value,
        source_root=result.source_root,
    )
    layers = [
        OperatorLayerSummary(
            name="factual",
            status=result.factual_layer.status.value,
            details={
                "modules_scanned": result.factual_layer.modules_scanned,
                "scan_errors": result.factual_layer.scan_errors,
            },
        ),
        OperatorLayerSummary(
            name="runtime",
            status=result.runtime_layer.status.value,
            details={"runtime_event_count": result.runtime_layer.runtime_event_count},
        ),
        OperatorLayerSummary(
            name="enrichment",
            status=result.enrichment_layer.status.value,
            details={
                "provider_configured": result.enrichment_layer.provider_configured,
                "modules_done": getattr(result.enrichment_layer, "modules_done", 0),
                "degraded_count": result.enrichment_layer.degraded_count,
            },
        ),
        OperatorLayerSummary(
            name="report",
            status=result.report_layer.status.value,
            details={"report_path": result.report_layer.report_path},
        ),
    ]
    scan_timestamp = getattr(result.factual_layer, "scanned_at", None) or report.get("scope", {}).get("scan_updated_at")
    artifacts = [
        OperatorArtifactSummary(
            kind=artifact.kind.value,
            path=artifact.path,
            required=artifact.required,
            exists=(run_dir / artifact.path).exists(),
            freshness=evaluate_path_freshness(run_dir / artifact.path, scan_timestamp),
        )
        for artifact in result.artifacts
    ]
    warnings = [issue.code for issue in result.limits if issue.severity.value in {"warning", "error"}]
    next_steps = [step.message for step in result.next_safe_steps]
    if not next_steps:
        report_steps = report.get("next_safe_steps")
        if isinstance(report_steps, list):
            next_steps = [str(item) for item in report_steps]
    return OperatorState(
        run=run_summary,
        layers=layers,
        artifacts=artifacts,
        modules=_module_rows_from_schema(schema, findings),
        warnings=warnings,
        next_safe_steps=next_steps,
    )
