from __future__ import annotations

from .models import ModuleFact


class ModulePolicyBase:
    INTERESTING_MODULE_TOKENS = (
        "app",
        "api",
        "main",
        "server",
        "service",
        "handler",
        "bridge",
        "store",
        "client",
        "runtime",
        "console",
        "operator",
        "mission",
        "control",
    )
    LOW_SIGNAL_MODULE_TOKENS = ("test", "tests", "example", "examples", "generated", "proto", "mock")
    GENERIC_MODULE_TOKENS = {
        "services",
        "service",
        "core",
        "shared",
        "src",
        "main",
        "app",
        "module",
        "handler",
        "orchestrator",
        "runtime",
    }
    PUBLIC_SURFACE_ENTRYPOINT_NAMES = {"main", "app", "cli", "run", "serve", "start"}
    PUBLIC_SURFACE_HELPER_SUFFIXES = {
        "status",
        "code",
        "reason",
        "result",
        "response",
        "request",
        "event",
        "payload",
        "config",
        "report",
    }
    MAX_PUBLIC_SYMBOLS = 5
    MAX_RESPONSIBILITIES = 5
    MAX_RESPONSIBILITY_LENGTH = 96
    MAX_PURPOSE_LENGTH = 96
    MAX_ACTIONABLE_HINTS = 3
    MAX_WARNINGS = 6
    MAX_PROCESSING_NOTES = 6
    PURPOSE_DANGLING_TAILS = {
        "and",
        "or",
        "with",
        "using",
        "via",
        "from",
        "for",
        "into",
        "over",
        "across",
        "through",
        "plus",
        "around",
        "structured",
    }
    PURPOSE_STOPWORDS = {
        "module",
        "system",
        "service",
        "layer",
    }

    @staticmethod
    def _first_sentence(text: str | None) -> str | None:
        if not text:
            return None
        normalized = " ".join(text.strip().split())
        if not normalized:
            return None
        for separator in (". ", "\n", "; "):
            if separator in normalized:
                normalized = normalized.split(separator, 1)[0].strip()
                break
        return normalized[:160].rstrip(".")

    @staticmethod
    def _method_names(module: ModuleFact) -> list[str]:
        return [method.name for klass in module.classes for method in klass.methods]

    @staticmethod
    def _module_has_structural_signal(module: ModuleFact, runtime_symbol_counts: dict[str, int]) -> bool:
        return bool(runtime_symbol_counts or module.functions or module.classes or module.imports)
