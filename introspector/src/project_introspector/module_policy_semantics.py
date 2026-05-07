from __future__ import annotations

from .models import ModuleFact
from .module_profiles import resolve_module_semantic_profile


class ModulePolicySemanticMixin:

    RESPONSIBILITY_EXACT_CODES = {
        'Process module-specific inputs into structured results.': 'resp.generic.process_inputs',
        'Handle one explicit module workflow step.': 'resp.generic.handle_step',
        'Run the main workflow exposed by this module.': 'resp.generic.run_main_workflow',
    }

    @classmethod
    def _purpose_code(cls, text: str | None, *, module: ModuleFact | None = None) -> str | None:
        normalized = cls._normalize_purpose(text)
        if not normalized:
            return None
        profile = resolve_module_semantic_profile(module) if module is not None else None
        if profile is not None:
            code = profile.purpose_code(normalized)
            if code:
                return code
        if normalized.startswith('Publishes ') and normalized.endswith(' updates for the surrounding runtime flow'):
            topic = normalized.removeprefix('Publishes ').removesuffix(' updates for the surrounding runtime flow').strip()
            if topic:
                return f'purpose.generic.publish_updates:{topic}'
        if normalized.startswith('Processes ') and normalized.endswith(' inputs into module-specific results'):
            topic = normalized.removeprefix('Processes ').removesuffix(' inputs into module-specific results').strip()
            if topic:
                return f'purpose.generic.process_inputs:{topic}'
        if normalized.startswith('Runs the ') and normalized.endswith(' workflow for this module'):
            topic = normalized.removeprefix('Runs the ').removesuffix(' workflow for this module').strip()
            if topic:
                return f'purpose.generic.run_workflow:{topic}'
        if normalized.startswith('Coordinates the ') and normalized.endswith(' entrypoint for this module'):
            topic = normalized.removeprefix('Coordinates the ').removesuffix(' entrypoint for this module').strip()
            if topic:
                return f'purpose.generic.coordinate_entrypoint:{topic}'
        return None

    @classmethod
    def _responsibility_code(cls, text: str, *, module: ModuleFact | None = None) -> str | None:
        normalized = cls._normalize_responsibility_text(text)
        if not normalized:
            return None
        profile = resolve_module_semantic_profile(module) if module is not None else None
        if profile is not None:
            code = profile.responsibility_code(normalized)
            if code:
                return code
        if normalized in cls.RESPONSIBILITY_EXACT_CODES:
            return cls.RESPONSIBILITY_EXACT_CODES[normalized]
        prefix = 'Implement the main '
        suffix = ' workflow exposed by this module.'
        if normalized.startswith(prefix) and normalized.endswith(suffix):
            topic = normalized.removeprefix(prefix).removesuffix(suffix).strip()
            if topic:
                return f'resp.generic.implement_main_workflow:{topic}'
        return None

    @classmethod
    def _responsibility_codes(cls, items: list[str], *, module: ModuleFact | None = None) -> list[str]:
        codes: list[str] = []
        for item in items:
            code = cls._responsibility_code(item, module=module)
            if code and code not in codes:
                codes.append(code)
        return codes

    @classmethod
    def _normalize_responsibility_text(cls, text: str) -> str | None:
        normalized = " ".join(text.strip().split())
        if not normalized:
            return None
        sentence = cls._first_sentence(normalized) or normalized
        for prefix in (
            "This module ",
            "The module ",
            "This code ",
            "The code ",
            "Responsible for ",
        ):
            if sentence.lower().startswith(prefix.lower()):
                sentence = sentence[len(prefix) :].strip()
                break
        sentence = sentence.strip(" -:;,.")
        if not sentence:
            return None
        if len(sentence) > cls.MAX_RESPONSIBILITY_LENGTH:
            limit = cls.MAX_RESPONSIBILITY_LENGTH - 3
            candidate = sentence[:limit]
            if " " in candidate:
                candidate = candidate.rsplit(" ", 1)[0]
            sentence = candidate.rstrip(" ,;:") + "..."
        sentence = sentence[:1].upper() + sentence[1:]
        if not sentence.endswith(("...", ".")):
            sentence += "."
        return sentence

    @classmethod
    def _normalize_responsibilities(cls, items: list[str]) -> list[str]:
        normalized_items: list[str] = []
        seen: set[str] = set()
        for item in items:
            normalized = cls._normalize_responsibility_text(item)
            if not normalized:
                continue
            key = normalized.lower().rstrip(".")
            if key in seen:
                continue
            seen.add(key)
            normalized_items.append(normalized)
        return normalized_items

    @classmethod
    def _normalize_purpose(cls, text: str | None) -> str | None:
        if not text:
            return None
        sentence = cls._first_sentence(text)
        if not sentence:
            return None
        sentence = " ".join(sentence.split()).strip(" -:;,. ")
        if not sentence:
            return None
        for prefix in (
            "This module ",
            "The module ",
            "This code ",
            "The code ",
        ):
            if sentence.lower().startswith(prefix.lower()):
                sentence = sentence[len(prefix) :].strip()
                break
        if len(sentence) > cls.MAX_PURPOSE_LENGTH:
            limit = cls.MAX_PURPOSE_LENGTH - 3
            candidate = sentence[:limit]
            if " " in candidate:
                candidate = candidate.rsplit(" ", 1)[0]
            sentence = candidate.rstrip(" ,;:") + "..."
        sentence = cls._finalize_purpose_phrase(sentence)
        if not sentence:
            return None
        sentence = sentence[:1].upper() + sentence[1:]
        sentence = sentence.rstrip(".")
        return sentence

    @classmethod
    def _finalize_purpose_phrase(cls, text: str) -> str | None:
        sentence = text.strip()
        if not sentence:
            return None
        had_ellipsis = sentence.endswith("...")
        if had_ellipsis:
            sentence = sentence[:-3].rstrip(" ,;:")
        while sentence:
            last_word = sentence.split()[-1].lower().strip(" ,;:-")
            if last_word not in cls.PURPOSE_DANGLING_TAILS:
                break
            if " " not in sentence:
                return None
            sentence = sentence.rsplit(" ", 1)[0].rstrip(" ,;:-")
        if not sentence:
            return None
        if had_ellipsis:
            sentence = sentence.rstrip(" ,;:-")
        return sentence

    @classmethod
    def _module_doc_hint(cls, module: ModuleFact) -> str | None:
        if module.docstring:
            return cls._first_sentence(module.docstring)
        top_level_classes = [klass for klass in module.classes if not klass.name.startswith("_")]
        substantial_classes = [
            klass
            for klass in top_level_classes
            if any(not method.name.startswith("_") for method in klass.methods)
            or len(klass.methods) >= 2
            or cls._first_sentence(klass.docstring)
        ]
        has_substantial_class = bool(substantial_classes)
        for klass in top_level_classes:
            if cls._is_helper_value_class(klass, has_substantial_class=has_substantial_class):
                continue
            hint = cls._first_sentence(klass.docstring)
            if hint:
                return hint
        for function in module.functions:
            hint = cls._first_sentence(function.docstring)
            if hint:
                return hint
        return None

    @classmethod
    def _module_topic(cls, module: ModuleFact) -> str | None:
        parts = [
            part
            for part in module.module_path.split(".")
            if part and part not in cls.GENERIC_MODULE_TOKENS
        ]
        if not parts:
            return None
        topic_parts = parts[-2:] if len(parts) >= 2 else parts
        return " ".join(part.replace("_", " ") for part in topic_parts)

    @classmethod
    def _method_names(cls, module: ModuleFact) -> list[str]:
        return [method.name for klass in module.classes for method in klass.methods]

    @classmethod
    def _derive_purpose(cls, module: ModuleFact, runtime_symbol_counts: dict[str, int]) -> str | None:
        has_structural_signal = bool(runtime_symbol_counts or module.functions or module.classes)
        doc_hint = cls._module_doc_hint(module)
        if doc_hint and has_structural_signal:
            return cls._normalize_purpose(doc_hint)

        profile = resolve_module_semantic_profile(module)
        profile_purpose = profile.derive_purpose(module, runtime_symbol_counts)
        if profile_purpose:
            return cls._normalize_purpose(profile_purpose)

        module_lower = module.module_path.lower()
        methods = {name.lower() for name in cls._method_names(module)}
        topic = cls._module_topic(module)
        if not has_structural_signal:
            return None

        if topic and any('publish' in name for name in methods):
            return cls._normalize_purpose(f'Publishes {topic} updates for the surrounding runtime flow.')
        if topic and any(name.startswith('process_') or name.startswith('handle_') for name in methods):
            return cls._normalize_purpose(f'Processes {topic} inputs into module-specific results.')
        if topic and any(name.startswith('run_') for name in methods):
            return cls._normalize_purpose(f'Runs the {topic} workflow for this module.')
        if module_lower.endswith('.main') and topic:
            return cls._normalize_purpose(f'Coordinates the {topic} entrypoint for this module.')
        return None

    @classmethod
    def _select_purpose(cls, current: str | None, derived: str | None) -> str | None:
        current = cls._normalize_purpose(current)
        derived = cls._normalize_purpose(derived)
        if not current:
            return derived
        if not derived:
            return current
        current_tail = current.split()[-1].lower().strip(" ,;:-") if current else ""
        if (
            len(current) > len(derived) + 18
            or ":" in current
            or current_tail in cls.PURPOSE_DANGLING_TAILS
        ):
            return derived
        return current

    @classmethod
    def _derive_responsibilities(
        cls,
        module: ModuleFact,
        runtime_symbol_counts: dict[str, int],
    ) -> list[str]:
        methods = {name.lower() for name in cls._method_names(module)}
        has_structural_signal = bool(runtime_symbol_counts or module.functions or module.classes)
        responsibilities: list[str] = []

        def add(item: str) -> None:
            if item and item not in responsibilities:
                responsibilities.append(item)

        profile = resolve_module_semantic_profile(module)
        for item in profile.derive_responsibilities(module, runtime_symbol_counts):
            add(item)

        if not responsibilities:
            if any(name.startswith('process_') for name in methods):
                add('Process module-specific inputs into structured results.')
            if any(name.startswith('handle_') for name in methods):
                add('Handle one explicit module workflow step.')
            if any(name.startswith('run_') for name in methods):
                add('Run the main workflow exposed by this module.')
        if not responsibilities and has_structural_signal and len(module.classes) == 1 and module.classes[0].methods:
            class_name = module.classes[0].name.replace('_', ' ')
            add(f'Implement the main {class_name} workflow exposed by this module.')
        return cls._normalize_responsibilities(responsibilities)[: cls.MAX_RESPONSIBILITIES]
