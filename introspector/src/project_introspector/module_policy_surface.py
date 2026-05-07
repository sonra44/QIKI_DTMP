from __future__ import annotations

from typing import Any

from .models import ModuleFact


class ModulePolicySurfaceMixin:
    @staticmethod
    def _module_symbol_catalog(module: ModuleFact) -> dict[str, str]:
        catalog: dict[str, str] = {}
        for function in module.functions:
            catalog[function.qualified_name] = function.qualified_name
            catalog[function.name] = function.qualified_name
        for klass in module.classes:
            catalog[klass.qualified_name] = klass.qualified_name
            catalog[klass.name] = klass.qualified_name
            for method in klass.methods:
                catalog[method.qualified_name] = method.qualified_name
                catalog[method.name] = method.qualified_name
                catalog[f"{klass.name}.{method.name}"] = method.qualified_name
        return catalog

    @staticmethod
    def _canonicalize_symbols(candidates: list[str], catalog: dict[str, str]) -> list[str]:
        resolved: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            value = candidate.strip()
            if not value:
                continue
            canonical = catalog.get(value)
            if canonical is None:
                suffix = value.split(".")[-1]
                dotted_suffix = ".".join(value.split(".")[-2:])
                canonical = catalog.get(dotted_suffix) or catalog.get(suffix)
                if canonical is None:
                    for known in set(catalog.values()):
                        if known.endswith(value) or known.endswith(dotted_suffix):
                            canonical = known
                            break
            if canonical and canonical not in seen:
                seen.add(canonical)
                resolved.append(canonical)
        return resolved

    @staticmethod
    def _canonicalize_dependencies(candidates: list[str], imports: list[str]) -> list[str]:
        resolved: list[str] = []
        seen: set[str] = set()
        available = list(dict.fromkeys(imports))
        for candidate in candidates:
            value = candidate.strip()
            if not value:
                continue
            canonical = None
            if value in available:
                canonical = value
            else:
                suffix = value.split(".")[-1]
                for imported in available:
                    if imported.endswith(value) or imported.endswith(suffix):
                        canonical = imported
                        break
            if canonical and canonical not in seen:
                seen.add(canonical)
                resolved.append(canonical)
        return resolved

    @staticmethod
    def _semantic_drift_ratio(original_count: int, resolved_count: int) -> float:
        if original_count <= 0:
            return 0.0
        lost = max(0, original_count - resolved_count)
        return lost / float(original_count)

    @staticmethod
    def _filter_public_symbols(candidates: list[str]) -> list[str]:
        if not candidates:
            return []
        non_mock = [candidate for candidate in candidates if not candidate.split(".")[-1].startswith("Mock")]
        return non_mock or candidates

    @classmethod
    def _canonical_public_symbols(
        cls,
        module: ModuleFact,
        candidates: list[str],
    ) -> list[str]:
        candidate_set = set(candidates)
        module_leaf = module.module_path.split(".")[-1]
        top_level_functions = [
            function.qualified_name
            for function in module.functions
            if not function.name.startswith("_")
        ]
        top_level_classes = [
            klass
            for klass in module.classes
            if not klass.name.startswith("_")
        ]
        substantial_classes = [
            klass
            for klass in top_level_classes
            if any(not method.name.startswith("_") for method in klass.methods)
            or len(klass.methods) >= 2
            or cls._first_sentence(klass.docstring)
        ]
        has_substantial_class = bool(substantial_classes)

        def class_score(klass: Any) -> tuple[int, str]:
            name_lower = klass.name.lower()
            public_method_count = sum(1 for method in klass.methods if not method.name.startswith("_"))
            score = 50 + public_method_count * 10 + len(klass.methods)
            if cls._first_sentence(klass.docstring):
                score += 15
            if name_lower.startswith("mock"):
                score -= 100
            if has_substantial_class and not public_method_count and len(klass.methods) <= 1:
                score -= 40
            if (
                has_substantial_class
                and any(name_lower.endswith(suffix) for suffix in cls.PUBLIC_SURFACE_HELPER_SUFFIXES)
            ):
                score -= 25
            return score, klass.qualified_name

        ranked_classes = [
            klass.qualified_name
            for klass in sorted(top_level_classes, key=class_score, reverse=True)
            if class_score(klass)[0] > 0
        ]
        ranked_functions = []
        for function in top_level_functions:
            name = function.split(".")[-1]
            score = 30
            if name in cls.PUBLIC_SURFACE_ENTRYPOINT_NAMES:
                score += 20
            ranked_functions.append((score, function))
        ranked_functions.sort(reverse=True)

        canonical: list[str] = []
        for qualified_name in ranked_classes:
            if qualified_name in candidate_set and qualified_name not in canonical:
                canonical.append(qualified_name)
        for _score, qualified_name in ranked_functions:
            if qualified_name in candidate_set and qualified_name not in canonical:
                canonical.append(qualified_name)
        if module_leaf in cls.PUBLIC_SURFACE_ENTRYPOINT_NAMES:
            for _score, qualified_name in ranked_functions:
                if len(canonical) >= cls.MAX_PUBLIC_SYMBOLS:
                    break
                name = qualified_name.split(".")[-1]
                if name in cls.PUBLIC_SURFACE_ENTRYPOINT_NAMES and qualified_name not in canonical:
                    canonical.append(qualified_name)

        if canonical:
            return canonical[: cls.MAX_PUBLIC_SYMBOLS]
        fallback = ranked_classes + [qualified_name for _score, qualified_name in ranked_functions]
        return fallback[: cls.MAX_PUBLIC_SYMBOLS]

    @classmethod
    def _public_surface_needs_warning(
        cls,
        module: ModuleFact,
        public_symbols: list[str],
    ) -> bool:
        if not public_symbols:
            return False
        top_level_function_names = {
            function.qualified_name
            for function in module.functions
            if not function.name.startswith("_")
        }
        top_level_classes = [
            klass
            for klass in module.classes
            if not klass.name.startswith("_")
        ]
        substantial_classes = [
            klass
            for klass in top_level_classes
            if any(not method.name.startswith("_") for method in klass.methods)
            or len(klass.methods) >= 2
            or cls._first_sentence(klass.docstring)
        ]
        has_substantial_class = bool(substantial_classes)
        top_level_class_names = {klass.qualified_name for klass in top_level_classes}
        helper_value_class_names = {
            klass.qualified_name
            for klass in top_level_classes
            if cls._is_helper_value_class(klass, has_substantial_class=has_substantial_class)
            or any(klass.name.lower().endswith(suffix) for suffix in cls.PUBLIC_SURFACE_HELPER_SUFFIXES)
        }
        top_level_symbols = top_level_function_names | top_level_class_names
        final_symbols = [symbol for symbol in public_symbols if symbol in top_level_symbols]
        if len(final_symbols) != len(public_symbols):
            return True
        if any(symbol.split(".")[-1].startswith(("Mock", "_")) for symbol in final_symbols):
            return True
        helper_symbols = [symbol for symbol in final_symbols if symbol in helper_value_class_names]
        substantial_surface = [
            symbol for symbol in final_symbols if symbol in top_level_class_names - helper_value_class_names
        ]
        if helper_symbols and substantial_surface:
            return True
        if len(helper_symbols) > 1:
            return True
        return False

    @staticmethod
    def _filter_cleanup_candidates(candidates: list[str], runtime_symbol_counts: dict[str, int]) -> list[str]:
        filtered: list[str] = []
        for candidate in candidates:
            symbol_name = candidate.split(".")[-1]
            owner_name = candidate.split(".")[-2] if "." in candidate else ""
            if runtime_symbol_counts.get(candidate, 0) > 0:
                continue
            if not symbol_name.startswith("_"):
                continue
            if owner_name[:1].isupper() and not owner_name.startswith(("Mock", "_")):
                continue
            filtered.append(candidate)
        return filtered

    @classmethod
    def _is_helper_value_class(cls, klass: Any, *, has_substantial_class: bool) -> bool:
        name_lower = klass.name.lower()
        public_method_count = sum(1 for method in klass.methods if not method.name.startswith("_"))
        return has_substantial_class and not public_method_count and any(
            name_lower.endswith(suffix) for suffix in cls.PUBLIC_SURFACE_HELPER_SUFFIXES
        )
