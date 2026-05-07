from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .models import LLMModuleAnalysis


@dataclass(slots=True)
class AnalyzerStatus:
    configured: bool
    provider_credentials_configured: bool | None = None
    provider_probe_status: str | None = None
    base_url: str | None = None
    default_model: str | None = None
    fallback_model: str | None = None
    app_name: str = "project-introspector"
    build_marker: str | None = None
    app_file: str | None = None
    app_file_mtime: str | None = None
    provider_name: str | None = None
    storage_layout: dict[str, str] = field(default_factory=dict)
    storage: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ModuleAnalysisArtifact:
    analysis: LLMModuleAnalysis | None = None
    artifact_path: Path | None = None
    detail_ref: "ArtifactReference | None" = None
    related_refs: list["ArtifactReference"] = field(default_factory=list)


@dataclass(slots=True)
class ArtifactReference:
    path: Path
    source_kind: str
    variant: str
    updated_at: str | None = None
    exists: bool = False
    doc_key: str | None = None
    module_path: str | None = None


@dataclass(slots=True)
class ModuleOverviewRow:
    module_path: str
    file_path: str
    status: str
    enrichment_state: str
    degraded: bool
    warnings_count: int
    runtime_signal: bool
    runtime_count: int
    purpose: str
    artifact_path: Path | None = None


@dataclass(slots=True)
class OverviewStats:
    project_name: str
    module_count: int
    runtime_evidence_count: int
    degraded_count: int
    warning_heavy_count: int
    status_counts: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class LivePassSummary:
    summary_path: Path | None = None
    status_path: Path | None = None
    artifact_paths: list[Path] = field(default_factory=list)
    artifact_refs: list[ArtifactReference] = field(default_factory=list)
    project_name: str | None = None
    output_dir: str | None = None
    provider_configured: bool | None = None
    factual_refresh_status: str | None = None
    enrichment_status: str | None = None
    modules_requested: int = 0
    modules_done: int = 0
    modules_degraded: int = 0
    modules_failed: int = 0


@dataclass(slots=True)
class ProjectScanSummary:
    summary_path: Path | None = None
    project_name: str | None = None
    source_root: str | None = None
    modules_scanned: int = 0
    scan_errors: int = 0
    scanned_at: str | None = None
    output_dir: str | None = None
    factual_status: str | None = None
    schema_ready: bool = False
    runtime_merged: bool = False
    runtime_event_count: int = 0


@dataclass(slots=True)
class SubprocessResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
