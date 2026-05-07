from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CodeLocation(BaseModel):
    file_path: str
    module_path: str
    lineno: int | None = None
    end_lineno: int | None = None


class ParameterFact(BaseModel):
    name: str
    annotation: str | None = None
    has_default: bool = False


class FunctionFact(BaseModel):
    name: str
    qualified_name: str
    location: CodeLocation
    parameters: list[ParameterFact] = Field(default_factory=list)
    returns: str | None = None
    decorators: list[str] = Field(default_factory=list)
    docstring: str | None = None
    is_async: bool = False


class AttributeFact(BaseModel):
    class_name: str | None = None
    qualified_name: str
    attribute_name: str
    attribute_kind: Literal["class", "instance"]
    defined_in: str | None = None
    annotation: str | None = None
    location: CodeLocation


class ClassFact(BaseModel):
    name: str
    qualified_name: str
    location: CodeLocation
    bases: list[str] = Field(default_factory=list)
    decorators: list[str] = Field(default_factory=list)
    methods: list[FunctionFact] = Field(default_factory=list)
    attributes: list[AttributeFact] = Field(default_factory=list)
    docstring: str | None = None


class ImportFact(BaseModel):
    raw_import: str
    normalized_import: str
    import_kind: Literal["absolute", "relative", "future"] = "absolute"
    root: str | None = None
    imported_names: list[str] = Field(default_factory=list)
    is_from_import: bool = False
    location: CodeLocation


class FastAPIRouteFact(BaseModel):
    method: str
    path: str
    qualified_name: str
    decorator: str
    app_name: str | None = None
    location: CodeLocation


class EnvVarFact(BaseModel):
    name: str
    access_kind: Literal["getenv", "get", "getitem", "setdefault"]
    default: str | None = None
    location: CodeLocation


class CliOptionFact(BaseModel):
    option_strings: list[str] = Field(default_factory=list)
    dest: str | None = None
    default: str | None = None
    required: bool | None = None
    action: str | None = None
    help: str | None = None
    location: CodeLocation


class PydanticFieldFact(BaseModel):
    name: str
    annotation: str | None = None
    has_default: bool = False
    default: str | None = None


class PydanticModelFact(BaseModel):
    name: str
    qualified_name: str
    bases: list[str] = Field(default_factory=list)
    fields: list[PydanticFieldFact] = Field(default_factory=list)
    location: CodeLocation


class ModuleFact(BaseModel):
    module_path: str
    file_path: str
    file_hash: str
    imports: list[str] = Field(default_factory=list)
    import_facts: list[ImportFact] = Field(default_factory=list)
    functions: list[FunctionFact] = Field(default_factory=list)
    classes: list[ClassFact] = Field(default_factory=list)
    assignments: list[str] = Field(default_factory=list)
    docstring: str | None = None
    fastapi_routes: list[FastAPIRouteFact] = Field(default_factory=list)
    env_vars: list[EnvVarFact] = Field(default_factory=list)
    cli_options: list[CliOptionFact] = Field(default_factory=list)
    pydantic_models: list[PydanticModelFact] = Field(default_factory=list)
    class_attributes: list[AttributeFact] = Field(default_factory=list)

    @staticmethod
    def hash_source(source: str) -> str:
        return sha256(source.encode("utf-8")).hexdigest()


class ScanError(BaseModel):
    file_path: str
    module_path: str
    error_type: str
    message: str


class RuntimeEvent(BaseModel):
    event_type: Literal["call", "error"]
    project_name: str
    module_path: str
    qualified_name: str
    timestamp: datetime = Field(default_factory=utc_now)
    duration_ms: float | None = None
    args_shape: dict[str, str] = Field(default_factory=dict)
    result_shape: str | None = None
    exception_type: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class StaticScanEnvelope(BaseModel):
    project_name: str
    scanned_at: datetime = Field(default_factory=utc_now)
    root_path: str
    modules: list[ModuleFact]
    scan_errors: list[ScanError] = Field(default_factory=list)


class DependencyEdge(BaseModel):
    source: str
    target: str
    kind: Literal["import", "runtime_call"]
    weight: int = 1


class SymbolSummary(BaseModel):
    qualified_name: str
    symbol_type: Literal["function", "class"]
    module_path: str
    runtime_call_count: int = 0
    has_docstring: bool = False


class ProjectSchema(BaseModel):
    project_name: str
    built_at: datetime = Field(default_factory=utc_now)
    module_count: int
    function_count: int
    class_count: int
    runtime_event_count: int
    modules: list[ModuleFact]
    edges: list[DependencyEdge]
    symbols: list[SymbolSummary]
    notes: list[str] = Field(default_factory=list)


ModuleStatus = Literal["active", "low-signal", "stale-risk", "needs-attention", "safe-to-ignore"]
ActivityStatus = Literal["active", "low-signal", "safe-to-ignore"]
AttentionStatus = Literal["normal", "stale-risk", "needs-attention"]
RuntimeSignalStatus = Literal["observed", "missing"]
SemanticConfidenceStatus = Literal["grounded", "limited", "degraded"]


class LLMModuleAnalysis(BaseModel):
    module_path: str
    purpose: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    public_symbols: list[str] = Field(default_factory=list)
    outbound_dependencies: list[str] = Field(default_factory=list)
    runtime_hotspots: list[str] = Field(default_factory=list)
    stale_doc_signals: list[str] = Field(default_factory=list)
    cleanup_candidates: list[str] = Field(default_factory=list)
    status: ModuleStatus | None = None
    actionable_hints: list[str] = Field(default_factory=list)
    processing_notes: list[str] = Field(default_factory=list)
    raw_text: str | None = None
    llm_model: str | None = None
    llm_provider: str = "openrouter"
    degraded: bool = False
    warnings: list[str] = Field(default_factory=list)
    warning_codes: list[str] = Field(default_factory=list)
    actionable_hint_codes: list[str] = Field(default_factory=list)
    processing_note_codes: list[str] = Field(default_factory=list)
    purpose_code: str | None = None
    responsibility_codes: list[str] = Field(default_factory=list)
    semantic_profile: str | None = None
    activity_status: ActivityStatus | None = None
    attention_status: AttentionStatus | None = None
    runtime_signal_status: RuntimeSignalStatus | None = None
    semantic_confidence_status: SemanticConfidenceStatus | None = None
    requested_model: str | None = None
    provider_model_used: str | None = None
    provider_error_kind: str | None = None
    provider_status_code: int | None = None
    provider_retryable: bool | None = None
    provider_structured_output_used: bool | None = None
    provider_structured_output_fallback: bool | None = None
    payload_limits: dict[str, Any] = Field(default_factory=dict)


class LLMProjectAnalysis(BaseModel):
    project_name: str
    purpose: str | None = None
    architecture_shape: str | None = None
    key_entrypoints: list[str] = Field(default_factory=list)
    critical_modules: list[str] = Field(default_factory=list)
    external_dependencies: list[str] = Field(default_factory=list)
    dead_or_low_signal_modules: list[str] = Field(default_factory=list)
    documentation_candidates: list[str] = Field(default_factory=list)
    cleanup_candidates: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    raw_text: str | None = None
    llm_model: str | None = None
    llm_provider: str = "openrouter"
    degraded: bool = False
    warnings: list[str] = Field(default_factory=list)
    warning_codes: list[str] = Field(default_factory=list)
    processing_note_codes: list[str] = Field(default_factory=list)
    policy_removed_items: dict[str, list[str]] = Field(default_factory=dict)
    requested_model: str | None = None
    provider_model_used: str | None = None
    provider_error_kind: str | None = None
    provider_status_code: int | None = None
    provider_retryable: bool | None = None
    provider_structured_output_used: bool | None = None
    provider_structured_output_fallback: bool | None = None
    payload_limits: dict[str, Any] = Field(default_factory=dict)


ProjectSnapshot = StaticScanEnvelope
