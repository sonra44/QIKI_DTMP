from __future__ import annotations

from dataclasses import dataclass, field

from .import_normalization import normalized_import_targets
from .models import LLMProjectAnalysis, ProjectSchema


@dataclass(frozen=True)
class ProjectAnalysisPolicyResult:
    analysis: LLMProjectAnalysis
    removed_items: dict[str, list[str]] = field(default_factory=dict)
    warning_codes: list[str] = field(default_factory=list)
    processing_note_codes: list[str] = field(default_factory=list)
    degraded: bool = False


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value))


def _filter_known(values: list[str], known: set[str]) -> tuple[list[str], list[str]]:
    kept = [value for value in _dedupe(values) if value in known]
    removed = [value for value in _dedupe(values) if value not in known]
    return kept, removed


def _external_roots(schema: ProjectSchema) -> set[str]:
    module_index = {module.module_path for module in schema.modules}
    internal_roots = {module.module_path.split('.')[0] for module in schema.modules if module.module_path}
    roots: set[str] = set()
    for module in schema.modules:
        targets = [fact.normalized_import for fact in module.import_facts if fact.normalized_import]
        if not targets:
            targets = normalized_import_targets(module.module_path, module.imports)
        for imported in targets:
            root = imported.split('.')[0]
            if root and imported not in module_index and root not in internal_roots and root != '__future__':
                roots.add(root)
    return roots


def _entrypoint_known(value: str, *, modules: set[str], symbols: set[str]) -> bool:
    if value in modules or value in symbols:
        return True
    return any(value.startswith(f'{module}:') or value.startswith(f'{module}.') for module in modules)


def apply_project_analysis_policy(
    analysis: LLMProjectAnalysis,
    schema: ProjectSchema,
) -> ProjectAnalysisPolicyResult:
    known_modules = {module.module_path for module in schema.modules}
    known_symbols = {symbol.qualified_name for symbol in schema.symbols}
    external_roots = _external_roots(schema)
    removed_items: dict[str, list[str]] = {}
    warning_codes: list[str] = []
    processing_note_codes: list[str] = []

    analysis.project_name = schema.project_name

    analysis.critical_modules, removed = _filter_known(analysis.critical_modules, known_modules)
    if removed:
        removed_items['critical_modules'] = removed
        warning_codes.append('project_policy_removed_unknown_critical_module')

    analysis.dead_or_low_signal_modules, removed = _filter_known(
        analysis.dead_or_low_signal_modules,
        known_modules,
    )
    if removed:
        removed_items['dead_or_low_signal_modules'] = removed
        warning_codes.append('project_policy_removed_unknown_low_signal_module')

    external_kept = [value for value in _dedupe(analysis.external_dependencies) if value in external_roots]
    external_removed = [value for value in _dedupe(analysis.external_dependencies) if value not in external_roots]
    analysis.external_dependencies = external_kept
    if external_removed:
        removed_items['external_dependencies'] = external_removed
        warning_codes.append('project_policy_removed_unknown_external_dependency')

    entry_kept = [
        value for value in _dedupe(analysis.key_entrypoints)
        if _entrypoint_known(value, modules=known_modules, symbols=known_symbols)
    ]
    entry_removed = [value for value in _dedupe(analysis.key_entrypoints) if value not in entry_kept]
    analysis.key_entrypoints = entry_kept
    if entry_removed:
        removed_items['key_entrypoints'] = entry_removed
        warning_codes.append('project_policy_removed_unknown_entrypoint')

    cleanup_kept = [
        value for value in _dedupe(analysis.cleanup_candidates)
        if value in known_modules or value in known_symbols
    ]
    cleanup_removed = [value for value in _dedupe(analysis.cleanup_candidates) if value not in cleanup_kept]
    analysis.cleanup_candidates = cleanup_kept
    if cleanup_removed:
        removed_items['cleanup_candidates'] = cleanup_removed
        warning_codes.append('project_policy_removed_unknown_cleanup_candidate')
    if cleanup_kept:
        warning_codes.append('project_policy_cleanup_requires_manual_review')

    analysis.documentation_candidates = _dedupe(analysis.documentation_candidates)
    analysis.risks = _dedupe(analysis.risks)
    analysis.recommended_next_steps = _dedupe(analysis.recommended_next_steps)

    removed_count = sum(len(items) for items in removed_items.values())
    declared_count = sum(
        len(values)
        for values in (
            analysis.critical_modules,
            analysis.dead_or_low_signal_modules,
            analysis.external_dependencies,
            analysis.key_entrypoints,
            analysis.cleanup_candidates,
        )
    ) + removed_count
    degraded = analysis.degraded or removed_count >= 3 or (removed_count / max(declared_count, 1)) >= 0.3
    if degraded and removed_count:
        warning_codes.append('project_policy_severe_grounding_drift')

    if schema.runtime_event_count == 0 and analysis.dead_or_low_signal_modules:
        warning_codes.append('project_policy_runtime_absence_not_dead_code')

    analysis.degraded = degraded
    analysis.policy_removed_items = {key: _dedupe(values) for key, values in removed_items.items()}
    analysis.warning_codes = _dedupe([*analysis.warning_codes, *warning_codes])
    if analysis.warning_codes and not analysis.warnings:
        analysis.warnings = [code.replace('_', ' ') for code in analysis.warning_codes]
    return ProjectAnalysisPolicyResult(
        analysis=analysis,
        removed_items=analysis.policy_removed_items,
        warning_codes=analysis.warning_codes,
        processing_note_codes=processing_note_codes,
        degraded=analysis.degraded,
    )


def sanitize_project_analysis(
    analysis: LLMProjectAnalysis,
    schema: ProjectSchema,
) -> LLMProjectAnalysis:
    return apply_project_analysis_policy(analysis, schema).analysis
