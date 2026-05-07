from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RunMode(str, Enum):
    OFFLINE = "offline"
    ANALYZER_BACKED = "analyzer_backed"
    ENRICHMENT_REPLAY = "enrichment_replay"
    FULL = "full"


class RunStatus(str, Enum):
    COMPLETED = "completed"
    COMPLETED_WITH_LIMITS = "completed_with_limits"
    DEGRADED = "degraded"
    FAILED = "failed"


class LayerStatus(str, Enum):
    READY = "ready"
    ABSENT = "absent"
    SKIPPED = "skipped"
    PARTIAL = "partial"
    DEGRADED = "degraded"
    FAILED = "failed"


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ArtifactKind(str, Enum):
    STATIC_SNAPSHOT = "static_snapshot"
    SCAN_SUMMARY = "scan_summary"
    SCHEMA = "schema"
    REPORT = "report"
    LLM_STATUS = "llm_status"
    MODULE_FINDINGS_DIR = "module_findings_dir"
    PROGRESS_LOG = "progress_log"
    RUN_RESULT = "run_result"


class RunArtifactRef(BaseModel):
    kind: ArtifactKind
    path: str
    required: bool = False
    description: str | None = None


class RunIssue(BaseModel):
    code: str
    severity: IssueSeverity = IssueSeverity.INFO
    message: str
    layer: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class RunNextStep(BaseModel):
    code: str
    message: str
    priority: int = 100
    details: dict[str, Any] = Field(default_factory=dict)


class ProviderStatus(BaseModel):
    configured: bool = False
    provider_name: str | None = None
    requested_model: str | None = None
    fallback_model: str | None = None
    provider_model_used: str | None = None
    probe_status: LayerStatus | None = None
    error_kind: str | None = None
    message: str | None = None


class RunFactualLayer(BaseModel):
    status: LayerStatus
    modules_scanned: int = 0
    scan_errors: int = 0
    snapshot_path: str | None = None
    schema_path: str | None = None

    @field_validator("modules_scanned", "scan_errors")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("counts must be non-negative")
        return value


class RunRuntimeLayer(BaseModel):
    status: LayerStatus = LayerStatus.ABSENT
    runtime_event_count: int = 0
    latest_event_at: str | None = None

    @field_validator("runtime_event_count")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("runtime_event_count must be non-negative")
        return value


class RunEnrichmentLayer(BaseModel):
    status: LayerStatus = LayerStatus.SKIPPED
    provider_configured: bool = False
    llm_status_path: str | None = None
    module_findings_dir: str | None = None
    project_analysis_path: str | None = None
    degraded_count: int = 0
    provider: ProviderStatus | None = None

    @field_validator("degraded_count")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("degraded_count must be non-negative")
        return value


class RunReportLayer(BaseModel):
    status: LayerStatus
    report_path: str | None = None
    report_version: str | None = None


class RunResult(BaseModel):
    run_id: str
    project_name: str
    source_root: str
    mode: RunMode
    status: RunStatus
    started_at: str
    completed_at: str | None = None
    factual_layer: RunFactualLayer
    runtime_layer: RunRuntimeLayer = Field(default_factory=RunRuntimeLayer)
    enrichment_layer: RunEnrichmentLayer = Field(default_factory=RunEnrichmentLayer)
    report_layer: RunReportLayer
    artifacts: list[RunArtifactRef] = Field(default_factory=list)
    limits: list[RunIssue] = Field(default_factory=list)
    next_safe_steps: list[RunNextStep] = Field(default_factory=list)

    def required_artifact_paths(self) -> list[str]:
        return [artifact.path for artifact in self.artifacts if artifact.required]
