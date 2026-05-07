from __future__ import annotations

from typing import Any

from .provider_openai_compat import OpenAICompatibleSettings, OpenAICompatibleTransport

DEFAULT_OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
DEFAULT_OPENROUTER_MODEL = 'nvidia/nemotron-3-super-120b-a12b'
DEFAULT_OPENROUTER_FALLBACK_MODEL = 'nvidia/nemotron-3-nano-30b-a3b:free'


class OpenRouterSettings(OpenAICompatibleSettings):
    @classmethod
    def from_env(cls) -> 'OpenRouterSettings':
        settings = OpenAICompatibleSettings.from_env(
            prefix='LLM_PROVIDER_',
            default_base_url=DEFAULT_OPENROUTER_BASE_URL,
            default_model=DEFAULT_OPENROUTER_MODEL,
            default_fallback_model=DEFAULT_OPENROUTER_FALLBACK_MODEL,
            default_app_name='project-introspector',
            default_provider_name='openrouter',
            allow_openrouter_aliases=True,
        )
        return cls(**{field: getattr(settings, field) for field in cls.__dataclass_fields__})


class OpenRouterTransport(OpenAICompatibleTransport):
    def _model_selector(self, selected_model: str) -> dict[str, Any]:
        if self.settings.fallback_model and self.settings.fallback_model != selected_model:
            return {'models': [selected_model, self.settings.fallback_model]}
        return {'model': selected_model}

    def _structured_payload(
        self,
        *,
        selected_model: str,
        temperature: float,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        payload = super()._structured_payload(
            selected_model=selected_model,
            temperature=temperature,
            messages=messages,
            schema_name=schema_name,
            schema=schema,
        )
        payload['plugins'] = [{'id': 'response-healing'}]
        payload['provider'] = {'require_parameters': True}
        return payload
