from __future__ import annotations

from .import_normalization import normalized_import_targets
from .models import LLMModuleAnalysis, ModuleFact
from .module_policy_base import ModulePolicyBase
from .module_policy_quality import ModulePolicyQualityMixin
from .module_policy_semantics import ModulePolicySemanticMixin
from .module_policy_surface import ModulePolicySurfaceMixin
from .module_profiles import resolve_module_semantic_profile


class ModuleAnalysisPolicy(
    ModulePolicyQualityMixin,
    ModulePolicySemanticMixin,
    ModulePolicySurfaceMixin,
    ModulePolicyBase,
):
    def _normalize_surface_fields(
        self,
        analysis: LLMModuleAnalysis,
        *,
        module: ModuleFact,
        runtime_symbol_counts: dict[str, int],
    ) -> dict[str, object]:
        catalog = self._module_symbol_catalog(module)
        resolved_public_symbols = self._canonicalize_symbols(analysis.public_symbols, catalog)
        if not resolved_public_symbols:
            resolved_public_symbols = [
                item
                for item in (
                    [function.qualified_name for function in module.functions]
                    + [klass.qualified_name for klass in module.classes]
                )
                if not item.split(".")[-1].startswith("_")
            ][:10]
        filtered_public_symbols = self._filter_public_symbols(resolved_public_symbols)
        canonical_public_symbols = self._canonical_public_symbols(
            module,
            filtered_public_symbols or resolved_public_symbols,
        )

        resolved_runtime_hotspots = self._canonicalize_symbols(analysis.runtime_hotspots, catalog)
        if runtime_symbol_counts:
            for qualified_name, _count in sorted(
                runtime_symbol_counts.items(),
                key=lambda item: (-item[1], item[0]),
            ):
                if qualified_name not in resolved_runtime_hotspots:
                    resolved_runtime_hotspots.append(qualified_name)

        resolved_cleanup = self._canonicalize_symbols(analysis.cleanup_candidates, catalog)
        filtered_cleanup = self._filter_cleanup_candidates(resolved_cleanup, runtime_symbol_counts)
        resolved_outbound_dependencies = self._canonicalize_dependencies(
            analysis.outbound_dependencies,
            normalized_import_targets(module.module_path, module.imports) if not module.import_facts else [fact.normalized_import for fact in module.import_facts if fact.normalized_import],
        )
        return {
            "resolved_public_symbols": resolved_public_symbols,
            "filtered_public_symbols": filtered_public_symbols,
            "canonical_public_symbols": canonical_public_symbols,
            "resolved_runtime_hotspots": resolved_runtime_hotspots,
            "resolved_cleanup": resolved_cleanup,
            "filtered_cleanup": filtered_cleanup,
            "resolved_outbound_dependencies": resolved_outbound_dependencies,
        }

    def _drift_repair_plan(
        self,
        analysis: LLMModuleAnalysis,
        *,
        resolved_public_symbols: list[str],
        resolved_runtime_hotspots: list[str],
        filtered_cleanup: list[str],
        resolved_outbound_dependencies: list[str],
    ) -> tuple[list[str], bool]:
        drift_signals = {
            "public_symbols": self._semantic_drift_ratio(
                len(analysis.public_symbols),
                len(resolved_public_symbols),
            ),
            "runtime_hotspots": self._semantic_drift_ratio(
                len(analysis.runtime_hotspots),
                len(resolved_runtime_hotspots),
            ),
            "cleanup_candidates": self._semantic_drift_ratio(
                len(analysis.cleanup_candidates),
                len(filtered_cleanup),
            ),
            "outbound_dependencies": self._semantic_drift_ratio(
                len(analysis.outbound_dependencies),
                len(resolved_outbound_dependencies),
            ),
        }
        severe_drift_fields = [
            field
            for field, ratio in drift_signals.items()
            if ratio >= 0.75 and getattr(analysis, field)
        ]
        critical_drift_fields = {"public_symbols", "runtime_hotspots", "outbound_dependencies"}
        degrade_for_drift = (
            len([field for field in severe_drift_fields if field in critical_drift_fields]) >= 1
            or len(severe_drift_fields) >= 2
        )
        return severe_drift_fields, degrade_for_drift

    def _sanitize_module_analysis(
        self,
        analysis: LLMModuleAnalysis,
        *,
        module: ModuleFact,
        runtime_symbol_counts: dict[str, int],
    ) -> LLMModuleAnalysis:
        surface = self._normalize_surface_fields(
            analysis,
            module=module,
            runtime_symbol_counts=runtime_symbol_counts,
        )
        resolved_public_symbols = surface["resolved_public_symbols"]
        filtered_public_symbols = surface["filtered_public_symbols"]
        canonical_public_symbols = surface["canonical_public_symbols"]
        resolved_runtime_hotspots = surface["resolved_runtime_hotspots"]
        resolved_cleanup = surface["resolved_cleanup"]
        filtered_cleanup = surface["filtered_cleanup"]
        resolved_outbound_dependencies = surface["resolved_outbound_dependencies"]
        warnings = list(analysis.warnings)
        original_warning_codes = list(analysis.warning_codes)
        processing_notes = list(analysis.processing_notes)
        if analysis.public_symbols and len(resolved_public_symbols) < len(analysis.public_symbols):
            processing_notes.append("Filtered non-declared symbols from public_symbols.")
        if filtered_public_symbols and len(filtered_public_symbols) < len(resolved_public_symbols):
            processing_notes.append(
                "Filtered mock/helper scaffolding from public_symbols when non-mock symbols were available."
            )
        if canonical_public_symbols and len(canonical_public_symbols) < len(
            filtered_public_symbols or resolved_public_symbols
        ):
            processing_notes.append("Reduced public_symbols to the canonical top-level public surface.")
        if analysis.cleanup_candidates and len(resolved_cleanup) < len(analysis.cleanup_candidates):
            processing_notes.append("Filtered cleanup candidates that were not declared module symbols.")
        if resolved_cleanup and len(filtered_cleanup) < len(resolved_cleanup):
            processing_notes.append("Filtered cleanup_candidates to private non-runtime symbols only.")
            warnings.append("Cleanup suggestions need manual review.")
        if analysis.runtime_hotspots and len(resolved_runtime_hotspots) < len(analysis.runtime_hotspots):
            processing_notes.append("Normalized runtime_hotspots to declared symbols plus observed runtime counts.")
        if analysis.outbound_dependencies and len(resolved_outbound_dependencies) < len(
            analysis.outbound_dependencies
        ):
            processing_notes.append(
                "Filtered outbound_dependencies to imports supported by static module context."
            )

        severe_drift_fields, degrade_for_drift = self._drift_repair_plan(
            analysis,
            resolved_public_symbols=resolved_public_symbols,
            resolved_runtime_hotspots=resolved_runtime_hotspots,
            filtered_cleanup=filtered_cleanup,
            resolved_outbound_dependencies=resolved_outbound_dependencies,
        )

        analysis.module_path = module.module_path
        analysis.public_symbols = canonical_public_symbols or filtered_public_symbols or resolved_public_symbols
        if self._public_surface_needs_warning(module, analysis.public_symbols):
            warnings.append("Public surface may be noisy before normalization.")
        analysis.runtime_hotspots = list(dict.fromkeys(resolved_runtime_hotspots))
        analysis.cleanup_candidates = filtered_cleanup

        normalized_imports = [fact.normalized_import for fact in module.import_facts if fact.normalized_import] or normalized_import_targets(module.module_path, module.imports)
        analysis.outbound_dependencies = resolved_outbound_dependencies or normalized_imports[:20]
        original_purpose = self._normalize_purpose(analysis.purpose)
        derived_purpose = self._derive_purpose(module, runtime_symbol_counts)
        analysis.purpose = self._select_purpose(original_purpose, derived_purpose)
        if not original_purpose and analysis.purpose:
            processing_notes.append("Derived purpose conservatively from module structure and runtime hints.")
        elif (
            original_purpose
            and derived_purpose
            and analysis.purpose == derived_purpose
            and original_purpose != derived_purpose
        ):
            processing_notes.append("Reduced purpose to a shorter grounded module summary.")
        normalized_responsibilities = self._normalize_responsibilities(analysis.responsibilities)
        if len(normalized_responsibilities) > self.MAX_RESPONSIBILITIES:
            processing_notes.append("Reduced responsibilities to 2-5 concise grounded bullets.")
        derived_responsibilities = self._derive_responsibilities(module, runtime_symbol_counts)
        prefer_derived_responsibilities = (
            len(normalized_responsibilities) > self.MAX_RESPONSIBILITIES
            or any(item.endswith("...") for item in normalized_responsibilities)
        )
        if normalized_responsibilities and not prefer_derived_responsibilities:
            analysis.responsibilities = normalized_responsibilities[: self.MAX_RESPONSIBILITIES]
        elif derived_responsibilities:
            analysis.responsibilities = derived_responsibilities
            if normalized_responsibilities:
                processing_notes.append(
                    "Reduced responsibilities to a compact grounded shape using deterministic module hints."
                )
            else:
                processing_notes.append(
                    "Derived responsibilities conservatively from declared symbols, imports, and runtime hints."
                )
        else:
            analysis.responsibilities = normalized_responsibilities[: self.MAX_RESPONSIBILITIES]
        if runtime_symbol_counts and not analysis.runtime_hotspots:
            analysis.degraded = True
            warnings.append("Observed runtime signal could not be preserved from the model output.")
        if degrade_for_drift:
            analysis.degraded = True
            warnings.append(
                "Semantic drift was high for: " + ", ".join(sorted(severe_drift_fields)) + "."
            )
        if not runtime_symbol_counts:
            warnings.append(
                "No observed runtime signal for this module; analysis is based on static structure only."
            )
        if not module.docstring:
            warnings.append(
                "Module has no docstring; purpose inference relies on names, imports, and symbol structure."
            )
        if not analysis.purpose and not analysis.responsibilities:
            analysis.degraded = True
            warnings.append(
                "Purpose and responsibilities were empty; module-analysis semantic signal is low."
            )
        if analysis.degraded and not analysis.purpose:
            warnings.append("Purpose was left empty because semantic confidence was low.")
        analysis.semantic_profile = resolve_module_semantic_profile(module).name
        (
            analysis.activity_status,
            analysis.attention_status,
            analysis.runtime_signal_status,
            analysis.semantic_confidence_status,
        ) = self._derive_status_axes(
            module,
            runtime_symbol_counts=runtime_symbol_counts,
            degraded=analysis.degraded,
            warnings=warnings,
        )
        analysis.status = self._derive_module_status(
            module,
            runtime_symbol_counts=runtime_symbol_counts,
            degraded=analysis.degraded,
            warnings=warnings,
        )
        analysis.actionable_hints = self._derive_actionable_hints(
            module,
            runtime_symbol_counts=runtime_symbol_counts,
            degraded=analysis.degraded,
            warnings=warnings,
            processing_notes=processing_notes,
            status=analysis.status,
        )
        analysis.warnings = self._normalize_warnings(
            warnings,
            actionable_hints=analysis.actionable_hints,
        )
        analysis.processing_notes = self._normalize_processing_notes(processing_notes)
        analysis.warning_codes = list(dict.fromkeys([*original_warning_codes, *self._warning_codes(analysis.warnings)]))
        analysis.processing_note_codes = self._processing_note_codes(analysis.processing_notes)
        analysis.actionable_hint_codes = self._actionable_hint_codes(analysis.actionable_hints)
        analysis.purpose_code = self._purpose_code(analysis.purpose, module=module)
        analysis.responsibility_codes = self._responsibility_codes(analysis.responsibilities, module=module)
        return analysis
