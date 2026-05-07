from __future__ import annotations

from project_introspector.models import LLMModuleAnalysis


def test_generic_semantic_gate_repairs_runtime_surface_and_cleanup(policy_client, introspector_modules) -> None:
    target = introspector_modules["project_introspector.runtime"]
    analysis = LLMModuleAnalysis(
        module_path="wrong.path",
        purpose=None,
        responsibilities=[],
        public_symbols=["instrument_function", "ghost_symbol"],
        outbound_dependencies=["inspect", "ghost.dep"],
        runtime_hotspots=["ghost.hotspot"],
        cleanup_candidates=["ghost.cleanup", "project_introspector.runtime._emit_safely"],
    )

    repaired = policy_client._sanitize_module_analysis(
        analysis,
        module=target,
        runtime_symbol_counts={"project_introspector.runtime.instrument_function": 2},
    )

    assert repaired.semantic_profile == "base"
    assert repaired.purpose == "Best-effort OpenTelemetry setup"
    assert repaired.responsibilities == ["Implement the main NullContext workflow exposed by this module."]
    assert repaired.public_symbols == ["project_introspector.runtime.instrument_function"]
    assert repaired.runtime_hotspots == ["project_introspector.runtime.instrument_function"]
    assert repaired.cleanup_candidates == ["project_introspector.runtime._emit_safely"]
    assert repaired.outbound_dependencies == ["inspect"]
    assert repaired.status == "active"
    assert repaired.warnings == ["missing module docstring"]
    assert repaired.processing_notes == [
        "public surface normalized to top-level API",
        "cleanup suggestions were narrowed",
        "dependencies filtered to static imports",
        "purpose derived from module signal",
        "responsibilities normalized to grounded bullets",
    ]
    assert repaired.responsibility_codes == ["resp.generic.implement_main_workflow:NullContext"]


def test_generic_semantic_gate_degrades_on_severe_drift(policy_client, introspector_modules) -> None:
    target = introspector_modules["project_introspector.runtime"]
    analysis = LLMModuleAnalysis(
        module_path="totally.wrong",
        purpose=None,
        public_symbols=["ghost_a", "ghost_b", "ghost_c"],
        outbound_dependencies=["ghost.dep", "ghost.other"],
        runtime_hotspots=["ghost.hotspot"],
        cleanup_candidates=["ghost_cleanup_a", "ghost_cleanup_b"],
    )

    repaired = policy_client._sanitize_module_analysis(
        analysis,
        module=target,
        runtime_symbol_counts={},
    )

    assert repaired.semantic_profile == "base"
    assert repaired.degraded is True
    assert any(warning.startswith("high semantic drift: ") for warning in repaired.warnings)
    assert repaired.public_symbols
    assert repaired.outbound_dependencies
