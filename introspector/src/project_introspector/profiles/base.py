from __future__ import annotations

from dataclasses import dataclass

from ..models import ModuleFact


@dataclass(frozen=True, slots=True)
class ModuleSemanticProfile:
    name: str = 'base'

    def matches(self, module: ModuleFact) -> bool:
        return False

    def derive_purpose(self, module: ModuleFact, runtime_symbol_counts: dict[str, int]) -> str | None:
        return None

    def derive_responsibilities(self, module: ModuleFact, runtime_symbol_counts: dict[str, int]) -> list[str]:
        return []

    def purpose_code(self, text: str | None) -> str | None:
        return None

    def responsibility_code(self, text: str | None) -> str | None:
        return None


BASE_MODULE_PROFILE = ModuleSemanticProfile()
