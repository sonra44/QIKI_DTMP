from __future__ import annotations

from project_introspector.module_profiles import resolve_module_semantic_profile


def test_all_introspector_modules_use_base_profile(introspector_modules) -> None:
    profile_names = {
        module_path: resolve_module_semantic_profile(module).name
        for module_path, module in introspector_modules.items()
    }

    assert profile_names
    assert set(profile_names.values()) == {"base"}
