from __future__ import annotations

from .models import ModuleFact
from .profiles import BASE_MODULE_PROFILE, ModuleSemanticProfile

def resolve_module_semantic_profile(module: ModuleFact) -> ModuleSemanticProfile:
    _ = module
    return BASE_MODULE_PROFILE
