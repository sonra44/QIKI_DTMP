from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

from qiki.services.operator_console.orion_v.modules.base import SubsystemModule


def _is_module_candidate(obj: Any) -> bool:
    if not inspect.isclass(obj):
        return False
    if inspect.isabstract(obj):
        return False
    return all(
        hasattr(obj, attr) for attr in ("slug", "title", "render_summary", "render_details", "sources_of_truth")
    )


def _discover_module_classes() -> list[type[Any]]:
    discovered: list[type[Any]] = []
    package_prefix = f"{__name__}."
    for info in pkgutil.iter_modules(__path__):
        module_name = info.name
        if module_name.startswith("_") or module_name in {"base", "common"}:
            continue
        module = importlib.import_module(f"{package_prefix}{module_name}")
        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if candidate.__module__ != module.__name__:
                continue
            if not _is_module_candidate(candidate):
                continue
            discovered.append(candidate)
    return discovered

def default_modules() -> list[SubsystemModule]:
    """Auto-discovered module list for ORION V F2 Systems."""
    modules: list[SubsystemModule] = []
    for cls in _discover_module_classes():
        try:
            instance = cls()
        except TypeError:
            continue
        modules.append(instance)
    return sorted(modules, key=lambda module: str(getattr(module, "title", "")).lower())


__all__ = ["SubsystemModule", "default_modules"]
