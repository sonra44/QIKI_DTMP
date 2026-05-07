from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from .models import ModuleFact, ModuleStatus, ProjectSchema


PROJECT_ANALYSIS_PROMPT = """You are a software architecture analyst.
You receive machine-extracted facts about a Python service.
Return JSON only. Do not wrap the JSON in markdown fences.
All human-readable explanatory text must be in Russian.
Keep identifiers, module paths, symbol names, and dependency names unchanged.
Do not invent modules, routes, APIs, or dependencies that are not present in the payload.
Be conservative when naming cleanup candidates.
If runtime_event_count is 0, do not treat missing runtime events as evidence of dead code.
Use the ranked_modules, likely_entrypoints, namespace_summary, and top_external_dependencies fields as the primary project signal.
Treat sampled_modules as supporting evidence only.
"""


MODULE_ANALYSIS_PROMPT = """You are a software architecture analyst.
You receive machine-extracted facts about one Python module.
Return JSON only. Do not wrap the JSON in markdown fences.
All human-readable explanatory text must be in Russian.
Keep identifiers, module paths, symbol names, and dependency names unchanged.
Do not invent symbols or dependencies that are not present in the payload.
Be conservative when naming cleanup candidates.
Only treat declared module-level functions, classes, and class methods as symbols.
Do not list local variables, temporary names, or implementation-only scratch values as public_symbols.
Use runtime_hotspot_candidates when they are present.
If the payload contains enough signal, set purpose to one short grounded sentence.
If the payload contains enough signal, set responsibilities to 2-5 short grounded bullets.
Prefer class docstrings, public symbol names, imports, and runtime hotspots over generic wording.
Keep purpose to a single concise sentence, not a mini-summary.
Keep responsibilities compact, action-oriented, and non-redundant.
If the payload is weak, leave purpose null and responsibilities empty instead of guessing.
"""


class ProjectAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str
    purpose: str | None = None
    architecture_shape: str | None = None
    key_entrypoints: list[str]
    critical_modules: list[str]
    external_dependencies: list[str]
    dead_or_low_signal_modules: list[str]
    documentation_candidates: list[str]
    cleanup_candidates: list[str]
    risks: list[str]
    recommended_next_steps: list[str]


class ModuleAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_path: str
    purpose: str | None = None
    responsibilities: list[str]
    public_symbols: list[str]
    outbound_dependencies: list[str]
    runtime_hotspots: list[str]
    stale_doc_signals: list[str]
    cleanup_candidates: list[str]
    status: ModuleStatus | None = None
    actionable_hints: list[str] = Field(default_factory=list)
    processing_notes: list[str] = Field(default_factory=list)


PROJECT_OUTPUT_SCHEMA = ProjectAnalysisOutput.model_json_schema()
MODULE_OUTPUT_SCHEMA = ModuleAnalysisOutput.model_json_schema()


class ModuleEnrichmentProvider(Protocol):
    provider_name: str

    def analyze_project_schema(self, schema: ProjectSchema, *, model: str | None = None, temperature: float = 0.1): ...

    def analyze_module(
        self,
        module: ModuleFact,
        *,
        runtime_symbol_counts: dict[str, int] | None = None,
        inbound_dependencies: list[str] | None = None,
        model: str | None = None,
        temperature: float = 0.1,
    ): ...
