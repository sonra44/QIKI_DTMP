from __future__ import annotations

from collections import Counter, defaultdict

from .models import ProjectSchema
from .tui_models import ModuleAnalysisArtifact, ModuleOverviewRow, OverviewStats


def build_module_rows(
    schema: ProjectSchema,
    analyses: dict[str, ModuleAnalysisArtifact],
) -> list[ModuleOverviewRow]:
    runtime_counts: dict[str, int] = defaultdict(int)
    for symbol in schema.symbols:
        runtime_counts[symbol.module_path] += symbol.runtime_call_count

    rows: list[ModuleOverviewRow] = []
    for module in sorted(schema.modules, key=lambda item: item.module_path):
        artifact = analyses.get(module.module_path)
        analysis = artifact.analysis if artifact else None
        status = analysis.status or "no-analysis" if analysis else "no-analysis"
        purpose = analysis.purpose or "" if analysis else ""
        warnings_count = len(analysis.warnings) if analysis else 0
        degraded = analysis.degraded if analysis else False
        runtime_count = runtime_counts.get(module.module_path, 0)
        rows.append(
            ModuleOverviewRow(
                module_path=module.module_path,
                file_path=module.file_path,
                status=status,
                enrichment_state=_enrichment_state(artifact),
                degraded=degraded,
                warnings_count=warnings_count,
                runtime_signal=runtime_count > 0,
                runtime_count=runtime_count,
                purpose=purpose,
                artifact_path=artifact.artifact_path if artifact else None,
            )
        )
    return rows


def compute_overview_stats(project_name: str, rows: list[ModuleOverviewRow]) -> OverviewStats:
    status_counts = Counter(row.status for row in rows)
    return OverviewStats(
        project_name=project_name,
        module_count=len(rows),
        runtime_evidence_count=sum(1 for row in rows if row.runtime_signal),
        degraded_count=sum(1 for row in rows if row.degraded),
        warning_heavy_count=sum(1 for row in rows if row.warnings_count > 0),
        status_counts=dict(sorted(status_counts.items())),
    )


def _enrichment_state(artifact: ModuleAnalysisArtifact | None) -> str:
    if artifact is None or artifact.analysis is None:
        return "pending"
    if artifact.analysis.degraded:
        return "degraded"
    return "done"


def filter_module_rows(
    rows: list[ModuleOverviewRow],
    *,
    search: str = "",
    status_filter: str = "all",
    degraded_only: bool = False,
    warnings_only: bool = False,
    runtime_filter: str = "all",
) -> list[ModuleOverviewRow]:
    search_term = search.strip().lower()
    filtered = rows
    if search_term:
        filtered = [row for row in filtered if search_term in row.module_path.lower()]
    if status_filter != "all":
        filtered = [row for row in filtered if row.status == status_filter]
    if degraded_only:
        filtered = [row for row in filtered if row.degraded]
    if warnings_only:
        filtered = [row for row in filtered if row.warnings_count > 0]
    if runtime_filter == "runtime-only":
        filtered = [row for row in filtered if row.runtime_signal]
    elif runtime_filter == "static-only":
        filtered = [row for row in filtered if not row.runtime_signal]
    elif runtime_filter == "no-runtime-evidence":
        filtered = [row for row in filtered if not row.runtime_signal]
    elif runtime_filter == "active-only":
        filtered = [row for row in filtered if row.status == "active"]
    elif runtime_filter == "stale-risk-only":
        filtered = [row for row in filtered if row.status == "stale-risk"]
    return filtered


def filter_report_findings(
    report: dict[str, object] | None,
    *,
    search: str = "",
    status_filter: str = "all",
    degraded_only: bool = False,
    warnings_only: bool = False,
) -> list[dict[str, object]]:
    if not report:
        return []
    raw_findings = report.get("module_findings")
    if not isinstance(raw_findings, list):
        return []
    findings = [item for item in raw_findings if isinstance(item, dict)]
    search_term = search.strip().lower()
    if search_term:
        findings = [
            item
            for item in findings
            if search_term in str(item.get("module_path") or "").lower()
            or search_term in str(item.get("purpose") or "").lower()
        ]
    if status_filter != "all":
        findings = [item for item in findings if item.get("status") == status_filter]
    if degraded_only:
        findings = [item for item in findings if bool(item.get("degraded"))]
    if warnings_only:
        findings = [item for item in findings if item.get("warnings")]
    return findings
