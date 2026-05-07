from __future__ import annotations

from pathlib import Path

import pytest

from project_introspector.llm_enrichment import OpenAICompatibleEnrichmentClient
from project_introspector.models import CodeLocation, DependencyEdge, FunctionFact, ModuleFact, ProjectSchema, SymbolSummary
from project_introspector.provider_errors import ProviderCallError, ProviderErrorKind
from project_introspector.provider_openai_compat import OpenAICompatibleSettings, ProviderCallMetadata


def _client() -> OpenAICompatibleEnrichmentClient:
    return OpenAICompatibleEnrichmentClient(
        OpenAICompatibleSettings(
            api_key="secret",
            base_url="https://provider.example/v1",
            default_model="demo-model",
            provider_name="demo-provider",
        )
    )


def _module() -> ModuleFact:
    location = CodeLocation(file_path="pkg/mod.py", module_path="pkg.mod", lineno=1)
    return ModuleFact(
        module_path="pkg.mod",
        file_path="pkg/mod.py",
        file_hash="hash",
        imports=["httpx"],
        functions=[FunctionFact(name="main", qualified_name="pkg.mod.main", location=location)],
        docstring="Demo module.",
    )


def _schema() -> ProjectSchema:
    module = _module()
    return ProjectSchema(
        project_name="demo",
        module_count=1,
        function_count=1,
        class_count=0,
        runtime_event_count=0,
        modules=[module],
        edges=[DependencyEdge(source="pkg.mod", target="httpx", kind="import")],
        symbols=[SymbolSummary(qualified_name="pkg.mod.main", symbol_type="function", module_path="pkg.mod")],
    )


@pytest.mark.parametrize("kind", [ProviderErrorKind.AUTH_ERROR, ProviderErrorKind.RATE_LIMITED, ProviderErrorKind.TIMEOUT])
def test_module_provider_failure_becomes_degraded_artifact(monkeypatch, kind: ProviderErrorKind) -> None:
    client = _client()

    def raise_error(**kwargs):
        raise ProviderCallError("provider failed", kind=kind, status_code=429 if kind == ProviderErrorKind.RATE_LIMITED else None)

    monkeypatch.setattr(client, "_best_effort_chat", raise_error)

    analysis = client.analyze_module(_module())

    assert analysis.degraded is True
    assert analysis.provider_error_kind == kind.value
    assert analysis.provider_retryable is (kind in {ProviderErrorKind.RATE_LIMITED, ProviderErrorKind.TIMEOUT})
    assert f"provider_{kind.value}" in analysis.warning_codes
    assert analysis.requested_model == "demo-model"


def test_project_provider_failure_becomes_degraded_artifact(monkeypatch) -> None:
    client = _client()

    def raise_error(**kwargs):
        raise ProviderCallError("bad token", kind=ProviderErrorKind.AUTH_ERROR, status_code=401, retryable=False)

    monkeypatch.setattr(client, "_best_effort_chat", raise_error)

    analysis = client.analyze_project_schema(_schema())

    assert analysis.degraded is True
    assert analysis.provider_error_kind == "auth_error"
    assert analysis.provider_status_code == 401
    assert analysis.provider_retryable is False
    assert "provider_auth_error" in analysis.warning_codes


def test_non_json_module_response_is_degraded(monkeypatch) -> None:
    client = _client()

    def bad_response(**kwargs):
        client.last_call_metadata = ProviderCallMetadata(
            requested_model="demo-model",
            provider_model_used="actual-model",
            structured_output_used=False,
            structured_output_fallback=True,
        )
        return {"raw_text": "not json at all"}, "not json at all"

    monkeypatch.setattr(client, "_best_effort_chat", bad_response)

    analysis = client.analyze_module(_module())

    assert analysis.degraded is True
    assert analysis.raw_text == "not json at all"
    assert "schema_mismatch" in analysis.warning_codes
    assert analysis.provider_model_used == "actual-model"


def test_json_in_markdown_fence_can_be_used(monkeypatch) -> None:
    client = _client()

    def fenced_response(**kwargs):
        return {"module_path": "pkg.mod", "purpose": "Demo", "responsibilities": ["Run demo."], "public_symbols": ["pkg.mod.main"]}, "```json\n{}\n```"

    monkeypatch.setattr(client, "_best_effort_chat", fenced_response)

    analysis = client.analyze_module(_module())

    assert analysis.module_path == "pkg.mod"
    assert analysis.degraded is False
    assert analysis.purpose is not None


def test_project_policy_filters_hallucinated_values(monkeypatch) -> None:
    client = _client()

    def hallucinated_response(**kwargs):
        return {
            "project_name": "demo",
            "critical_modules": ["pkg.mod", "pkg.fake"],
            "external_dependencies": ["httpx", "redis"],
            "cleanup_candidates": ["pkg.mod.main", "pkg.fake.dead"],
        }, "{}"

    monkeypatch.setattr(client, "_best_effort_chat", hallucinated_response)

    analysis = client.analyze_project_schema(_schema())

    assert analysis.critical_modules == ["pkg.mod"]
    assert analysis.external_dependencies == ["httpx"]
    assert analysis.cleanup_candidates == ["pkg.mod.main"]
    assert "pkg.fake" in analysis.policy_removed_items["critical_modules"]
    assert "redis" in analysis.policy_removed_items["external_dependencies"]
    assert analysis.degraded is True
