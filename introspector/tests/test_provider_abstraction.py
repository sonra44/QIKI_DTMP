from __future__ import annotations


from project_introspector.llm import OpenAICompatibleEnrichmentClient, OpenRouterClient, build_enrichment_client_from_env, get_provider_settings_from_env


def test_generic_provider_env_selects_openai_compatible(monkeypatch) -> None:
    monkeypatch.setenv('LLM_PROVIDER_BASE_URL', 'https://example.invalid/v1')
    monkeypatch.setenv('LLM_PROVIDER_MODEL', 'demo-model')
    monkeypatch.setenv('LLM_PROVIDER_NAME', 'demo-gateway')

    settings = get_provider_settings_from_env()
    client = build_enrichment_client_from_env()

    assert settings.provider_name == 'demo-gateway'
    assert isinstance(client, OpenAICompatibleEnrichmentClient)


def test_openrouter_is_preserved_as_default_provider(monkeypatch) -> None:
    monkeypatch.delenv('LLM_PROVIDER_BASE_URL', raising=False)
    monkeypatch.delenv('LLM_PROVIDER_MODEL', raising=False)
    monkeypatch.delenv('LLM_PROVIDER_NAME', raising=False)

    settings = get_provider_settings_from_env()
    client = build_enrichment_client_from_env()

    assert settings.provider_name == 'openrouter'
    assert isinstance(client, OpenRouterClient)



def test_inception_provider_preset_uses_mercury_defaults(monkeypatch) -> None:
    monkeypatch.setenv("INTROSPECTOR_PROVIDER", "inception")
    monkeypatch.setenv("INCEPTION_API_KEY", "secret")

    settings = get_provider_settings_from_env()
    client = build_enrichment_client_from_env()

    assert settings.provider_name == "inception"
    assert settings.base_url == "https://api.inceptionlabs.ai/v1"
    assert settings.default_model == "mercury-2"
    assert client.__class__.__name__ == "InceptionClient"
