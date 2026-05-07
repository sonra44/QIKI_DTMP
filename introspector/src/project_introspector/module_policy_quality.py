from __future__ import annotations

from .models import (
    ActivityStatus,
    AttentionStatus,
    ModuleFact,
    ModuleStatus,
    RuntimeSignalStatus,
    SemanticConfidenceStatus,
)


class ModulePolicyQualityMixin:
    @classmethod
    def _derive_status_axes(
        cls,
        module: ModuleFact,
        *,
        runtime_symbol_counts: dict[str, int],
        degraded: bool,
        warnings: list[str],
    ) -> tuple[ActivityStatus, AttentionStatus, RuntimeSignalStatus, SemanticConfidenceStatus]:
        has_runtime = bool(runtime_symbol_counts)
        has_doc = bool(module.docstring or any(cls._first_sentence(item.docstring) for item in module.classes))
        has_public_surface = any(not item.name.startswith("_") for item in module.functions) or any(
            not item.name.startswith("_") for item in module.classes
        )
        low_signal = not has_runtime and not has_doc

        runtime_signal_status: RuntimeSignalStatus = 'observed' if has_runtime else 'missing'
        semantic_confidence_status: SemanticConfidenceStatus
        if degraded:
            semantic_confidence_status = 'degraded'
        elif has_doc or has_runtime:
            semantic_confidence_status = 'grounded'
        else:
            semantic_confidence_status = 'limited'

        if has_runtime and has_public_surface:
            activity_status: ActivityStatus = 'active'
        elif low_signal and not has_public_surface:
            activity_status = 'safe-to-ignore'
        else:
            activity_status = 'low-signal'

        if degraded:
            attention_status: AttentionStatus = 'needs-attention'
        elif not has_runtime and any('docstring' in warning.lower() for warning in warnings):
            attention_status = 'stale-risk'
        else:
            attention_status = 'normal'

        return activity_status, attention_status, runtime_signal_status, semantic_confidence_status

    @classmethod
    def _derive_module_status(
        cls,
        module: ModuleFact,
        *,
        runtime_symbol_counts: dict[str, int],
        degraded: bool,
        warnings: list[str],
    ) -> ModuleStatus:
        activity_status, attention_status, _runtime_signal_status, _semantic_confidence_status = cls._derive_status_axes(
            module,
            runtime_symbol_counts=runtime_symbol_counts,
            degraded=degraded,
            warnings=warnings,
        )
        if attention_status == 'needs-attention':
            return 'needs-attention'
        if attention_status == 'stale-risk':
            return 'stale-risk'
        if activity_status == 'active':
            return 'active'
        if activity_status == 'safe-to-ignore':
            return 'safe-to-ignore'
        return 'low-signal'

    @classmethod
    def _derive_actionable_hints(
        cls,
        module: ModuleFact,
        *,
        runtime_symbol_counts: dict[str, int],
        degraded: bool,
        warnings: list[str],
        processing_notes: list[str],
        status: ModuleStatus,
    ) -> list[str]:
        hints: list[str] = []

        def add(text: str) -> None:
            if text and text not in hints:
                hints.append(text)

        if degraded:
            add("Review the module-analysis output before relying on it.")
        if not runtime_symbol_counts:
            add("Add one real runtime flow to confirm the live path.")
        elif status == "active":
            add("Treat this as an active path and verify changes with runtime evidence.")
        if not module.docstring:
            add("Add a short module docstring or contract note.")
        if any("public surface" in item.lower() for item in warnings):
            add("Keep the public surface compact and avoid helper leakage.")
        if any("cleanup" in item.lower() for item in [*warnings, *processing_notes]):
            add("Review cleanup candidates manually before deleting symbols.")
        if status == "safe-to-ignore":
            add("Defer work here unless this module re-enters a live path.")
        return hints[: cls.MAX_ACTIONABLE_HINTS]

    @staticmethod
    def _normalize_processing_note_text(text: str) -> tuple[str, str] | None:
        note = " ".join(text.split()).strip()
        if not note:
            return None
        lower = note.lower()
        if (
            "filtered non-declared symbols from public_symbols" in lower
            or "mock/helper scaffolding" in lower
            or "canonical top-level public surface" in lower
        ):
            return "public_surface", "public surface normalized to top-level API"
        if "cleanup_candidates" in lower or "cleanup candidates" in lower:
            return "cleanup", "cleanup suggestions were narrowed"
        if "runtime_hotspots" in lower:
            return "runtime_hotspots", "runtime hotspots normalized to observed symbols"
        if "outbound_dependencies" in lower:
            return "dependencies", "dependencies filtered to static imports"
        if "derived purpose conservatively" in lower or "reduced purpose" in lower:
            return "purpose", "purpose derived from module signal"
        if "derived responsibilities conservatively" in lower or "reduced responsibilities" in lower:
            return "responsibilities", "responsibilities normalized to grounded bullets"
        return note.lower().strip("."), note.rstrip(".").lower()

    @classmethod
    def _normalize_processing_notes(cls, items: list[str]) -> list[str]:
        normalized: list[str] = []
        seen_keys: set[str] = set()
        for item in items:
            normalized_item = cls._normalize_processing_note_text(item)
            if not normalized_item:
                continue
            key, text = normalized_item
            if key in seen_keys:
                continue
            seen_keys.add(key)
            normalized.append(text)
        return normalized[: cls.MAX_PROCESSING_NOTES]

    @classmethod
    def _normalize_warning_text(cls, text: str) -> tuple[str, str] | None:
        warning = " ".join(text.split()).strip()
        if not warning:
            return None
        lower = warning.lower()
        if lower.startswith("high semantic drift:"):
            fields = warning.split(":", 1)[1].strip().rstrip(".") if ":" in warning else ""
            if fields:
                return "semantic_drift", f"high semantic drift: {fields}"
            return "semantic_drift", "high semantic drift"
        if lower == "high semantic drift":
            return "semantic_drift", "high semantic drift"
        if "semantic drift was high" in lower:
            if ":" in warning:
                fields = warning.split(":", 1)[1].strip().rstrip(".")
                if fields:
                    return "semantic_drift", f"high semantic drift: {fields}"
            return "semantic_drift", "high semantic drift"
        if "purpose and responsibilities were empty" in lower or "semantic signal is low" in lower:
            return "semantic_signal", "semantic signal remains low"
        if "purpose was left empty" in lower:
            return "semantic_signal", "semantic signal remains low"
        if "no observed runtime signal" in lower:
            return "runtime_signal", "no runtime evidence"
        if "module has no docstring" in lower:
            return "docstring", "missing module docstring"
        if "public surface may be noisy" in lower:
            return "public_surface", "public surface may be noisy"
        if "cleanup suggestions need manual review" in lower:
            return "cleanup", "cleanup suggestions need manual review"
        return warning.lower().strip("."), warning.rstrip(".").lower()

    @classmethod
    def _normalize_warnings(
        cls,
        warnings: list[str],
        *,
        actionable_hints: list[str] | None = None,
    ) -> list[str]:
        normalized: list[str] = []
        seen_keys: set[str] = set()
        hint_text = " ".join((actionable_hints or [])).lower()
        for warning in warnings:
            normalized_item = cls._normalize_warning_text(warning)
            if not normalized_item:
                continue
            key, text = normalized_item
            if key in seen_keys:
                continue
            if key == "cleanup" and "cleanup candidates manually" in hint_text:
                pass
            seen_keys.add(key)
            normalized.append(text)
        return normalized[: cls.MAX_WARNINGS]

    @classmethod
    def _warning_codes(cls, warnings: list[str]) -> list[str]:
        codes: list[str] = []
        for item in warnings:
            normalized = cls._normalize_warning_text(item)
            if not normalized:
                continue
            code, _text = normalized
            if code not in codes:
                codes.append(code)
        return codes[: cls.MAX_WARNINGS]

    @classmethod
    def _processing_note_codes(cls, notes: list[str]) -> list[str]:
        codes: list[str] = []
        for item in notes:
            normalized = cls._normalize_processing_note_text(item)
            if not normalized:
                continue
            code, _text = normalized
            if code not in codes:
                codes.append(code)
        return codes[: cls.MAX_PROCESSING_NOTES]

    @classmethod
    def _actionable_hint_codes(cls, hints: list[str]) -> list[str]:
        mapping = {
            'Review the module-analysis output before relying on it.': 'review_output',
            'Add one real runtime flow to confirm the live path.': 'add_runtime_flow',
            'Treat this as an active path and verify changes with runtime evidence.': 'verify_active_path',
            'Add a short module docstring or contract note.': 'add_docstring',
            'Keep the public surface compact and avoid helper leakage.': 'keep_surface_compact',
            'Review cleanup candidates manually before deleting symbols.': 'review_cleanup',
            'Defer work here unless this module re-enters a live path.': 'defer_until_live',
        }
        codes: list[str] = []
        for item in hints:
            code = mapping.get(item)
            if code and code not in codes:
                codes.append(code)
        return codes[: cls.MAX_ACTIONABLE_HINTS]
