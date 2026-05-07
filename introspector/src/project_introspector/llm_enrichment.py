from __future__ import annotations

import json
import logging
import os
from typing import Any

from .llm_contracts import (
    MODULE_ANALYSIS_PROMPT,
    MODULE_OUTPUT_SCHEMA,
    PROJECT_ANALYSIS_PROMPT,
    PROJECT_OUTPUT_SCHEMA,
    ModuleEnrichmentProvider,
)
from .llm_payloads import compact_module_fact, compact_project_schema
from .models import LLMModuleAnalysis, LLMProjectAnalysis, ModuleFact, ProjectSchema
from .module_analysis_policy import ModuleAnalysisPolicy
from .project_analysis_policy import sanitize_project_analysis
from .provider_errors import ProviderCallError
from .provider_inception import InceptionSettings, InceptionTransport
from .provider_openai_compat import OpenAICompatibleSettings, OpenAICompatibleTransport
from .provider_openrouter import OpenRouterSettings, OpenRouterTransport

logger = logging.getLogger(__name__)

ProviderSettings = OpenAICompatibleSettings | OpenRouterSettings | InceptionSettings


def get_provider_settings_from_env() -> ProviderSettings:
    provider = (os.getenv('INTROSPECTOR_PROVIDER') or os.getenv('LLM_PROVIDER_NAME') or '').strip().lower()
    if provider in {'inception', 'mercury', 'mercury-2'} or os.getenv('INCEPTION_API_KEY'):
        return InceptionSettings.from_env()
    generic_present = any(
        os.getenv(name)
        for name in (
            'LLM_PROVIDER_BASE_URL',
            'LLM_PROVIDER_API_KEY',
            'LLM_PROVIDER_MODEL',
            'LLM_PROVIDER_NAME',
            'INTROSPECTOR_BASE_URL',
            'INTROSPECTOR_API_KEY',
            'INTROSPECTOR_MODEL',
        )
    )
    if generic_present:
        settings = OpenAICompatibleSettings.from_env()
        if os.getenv('INTROSPECTOR_API_KEY') and not settings.api_key:
            settings.api_key = os.getenv('INTROSPECTOR_API_KEY')
        if os.getenv('INTROSPECTOR_BASE_URL'):
            settings.base_url = os.getenv('INTROSPECTOR_BASE_URL', settings.base_url).rstrip('/')
        if os.getenv('INTROSPECTOR_MODEL'):
            settings.default_model = os.getenv('INTROSPECTOR_MODEL', settings.default_model)
        if os.getenv('INTROSPECTOR_FALLBACK_MODEL'):
            settings.fallback_model = os.getenv('INTROSPECTOR_FALLBACK_MODEL')
        if os.getenv('INTROSPECTOR_PROVIDER'):
            settings.provider_name = os.getenv('INTROSPECTOR_PROVIDER', settings.provider_name)
        return settings
    return OpenRouterSettings.from_env()


class _BaseEnrichmentClient(ModuleAnalysisPolicy):
    provider_name = 'provider'

    @staticmethod
    def compact_module_fact(
        module: ModuleFact,
        *,
        runtime_symbol_counts: dict[str, int] | None = None,
        inbound_dependencies: list[str] | None = None,
    ) -> dict[str, object]:
        return compact_module_fact(
            module,
            runtime_symbol_counts=runtime_symbol_counts,
            inbound_dependencies=inbound_dependencies,
        )

    def compact_project_schema(self, schema: ProjectSchema) -> dict[str, object]:
        return compact_project_schema(schema, policy=self)

    def _metadata_fields(self, selected_model: str) -> dict[str, Any]:
        metadata = getattr(self, 'last_call_metadata', None)
        return {
            'requested_model': selected_model,
            'provider_model_used': getattr(metadata, 'provider_model_used', None),
            'provider_structured_output_used': getattr(metadata, 'structured_output_used', None),
            'provider_structured_output_fallback': getattr(metadata, 'structured_output_fallback', None),
        }

    def _provider_error_fields(self, exc: ProviderCallError) -> dict[str, Any]:
        return {
            'provider_error_kind': exc.kind.value,
            'provider_status_code': exc.status_code,
            'provider_retryable': exc.retryable,
        }

    def _chat_result(self, **kwargs: Any) -> tuple[dict[str, Any], str]:
        result = self._best_effort_chat(**kwargs)
        if isinstance(result, tuple) and len(result) >= 2:
            return result[0], result[1]
        raise ValueError('Provider chat returned an unexpected result shape')

    @staticmethod
    def _raw_text_only_payload(parsed: dict[str, Any]) -> bool:
        return set(parsed.keys()) <= {'raw_text'}

    def analyze_project_schema(
        self,
        schema: ProjectSchema,
        *,
        model: str | None = None,
        temperature: float = 0.1,
    ) -> LLMProjectAnalysis:
        selected_model = model or self.settings.default_model
        payload = compact_project_schema(schema, policy=self)
        messages = [
            {'role': 'system', 'content': PROJECT_ANALYSIS_PROMPT},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, indent=2)},
        ]
        try:
            parsed, raw_text = self._chat_result(
                selected_model=selected_model,
                temperature=temperature,
                messages=messages,
                schema_name='project_analysis',
                schema=PROJECT_OUTPUT_SCHEMA,
            )
        except ProviderCallError as exc:
            return LLMProjectAnalysis(
                project_name=schema.project_name,
                raw_text=None,
                llm_model=selected_model,
                llm_provider=self.settings.provider_name,
                degraded=True,
                warnings=[f'LLM provider request failed: {exc.kind.value}: {exc.message}'],
                warning_codes=[f'provider_{exc.kind.value}'],
                payload_limits=dict(payload.get('payload_limits') or {}),
                **self._metadata_fields(selected_model),
                **self._provider_error_fields(exc),
            )
        if self._raw_text_only_payload(parsed):
            return sanitize_project_analysis(
                LLMProjectAnalysis(
                    project_name=schema.project_name,
                    raw_text=str(parsed.get('raw_text') or raw_text),
                    llm_model=selected_model,
                    llm_provider=self.settings.provider_name,
                    degraded=True,
                    warnings=['LLM response did not contain structured project analysis JSON.'],
                    warning_codes=['schema_mismatch'],
                    payload_limits=dict(payload.get('payload_limits') or {}),
                    **self._metadata_fields(selected_model),
                ),
                schema,
            )
        parsed['project_name'] = parsed.get('project_name') or schema.project_name
        parsed['llm_model'] = selected_model
        parsed['llm_provider'] = self.settings.provider_name
        parsed['payload_limits'] = payload.get('payload_limits') or {}
        parsed.update(self._metadata_fields(selected_model))
        try:
            analysis = LLMProjectAnalysis.model_validate(parsed)
        except Exception:
            return LLMProjectAnalysis(
                project_name=schema.project_name,
                raw_text=raw_text,
                llm_model=selected_model,
                llm_provider=self.settings.provider_name,
                degraded=True,
                warnings=['LLM response did not match the expected project analysis schema.'],
                warning_codes=['schema_mismatch'],
                payload_limits=dict(payload.get('payload_limits') or {}),
                **self._metadata_fields(selected_model),
            )
        return sanitize_project_analysis(analysis, schema)

    def analyze_module(
        self,
        module: ModuleFact,
        *,
        runtime_symbol_counts: dict[str, int] | None = None,
        inbound_dependencies: list[str] | None = None,
        model: str | None = None,
        temperature: float = 0.1,
    ) -> LLMModuleAnalysis:
        selected_model = model or self.settings.default_model
        payload = compact_module_fact(
            module,
            runtime_symbol_counts=runtime_symbol_counts,
            inbound_dependencies=inbound_dependencies,
        )
        messages = [
            {'role': 'system', 'content': MODULE_ANALYSIS_PROMPT},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, indent=2)},
        ]
        try:
            parsed, raw_text = self._chat_result(
                selected_model=selected_model,
                temperature=temperature,
                messages=messages,
                schema_name='module_analysis',
                schema=MODULE_OUTPUT_SCHEMA,
            )
        except ProviderCallError as exc:
            return LLMModuleAnalysis(
                module_path=module.module_path,
                llm_model=selected_model,
                llm_provider=self.settings.provider_name,
                degraded=True,
                warnings=[f'LLM provider request failed: {exc.kind.value}: {exc.message}'],
                warning_codes=[f'provider_{exc.kind.value}'],
                payload_limits=dict(payload.get('payload_limits') or {}),
                **self._metadata_fields(selected_model),
                **self._provider_error_fields(exc),
            )
        if self._raw_text_only_payload(parsed):
            return self._sanitize_module_analysis(
                LLMModuleAnalysis(
                    module_path=module.module_path,
                    raw_text=str(parsed.get('raw_text') or raw_text),
                    llm_model=selected_model,
                    llm_provider=self.settings.provider_name,
                    degraded=True,
                    warnings=['LLM response did not contain structured module analysis JSON.'],
                    warning_codes=['schema_mismatch'],
                    payload_limits=dict(payload.get('payload_limits') or {}),
                    **self._metadata_fields(selected_model),
                ),
                module=module,
                runtime_symbol_counts=runtime_symbol_counts or {},
            )
        parsed['module_path'] = parsed.get('module_path') or module.module_path
        parsed['llm_model'] = selected_model
        parsed['llm_provider'] = self.settings.provider_name
        parsed['payload_limits'] = payload.get('payload_limits') or {}
        parsed.update(self._metadata_fields(selected_model))
        try:
            analysis = LLMModuleAnalysis.model_validate(parsed)
        except Exception:
            return LLMModuleAnalysis(
                module_path=module.module_path,
                raw_text=raw_text,
                llm_model=selected_model,
                llm_provider=self.settings.provider_name,
                degraded=True,
                warnings=['LLM response did not match the expected module analysis schema.'],
                warning_codes=['schema_mismatch'],
                payload_limits=dict(payload.get('payload_limits') or {}),
                **self._metadata_fields(selected_model),
            )
        return self._sanitize_module_analysis(analysis, module=module, runtime_symbol_counts=runtime_symbol_counts or {})


class OpenAICompatibleEnrichmentClient(OpenAICompatibleTransport, _BaseEnrichmentClient):
    def __init__(self, settings: OpenAICompatibleSettings | None = None):
        self.settings = settings or OpenAICompatibleSettings.from_env()
        OpenAICompatibleTransport.__init__(self, self.settings)


class OpenRouterClient(OpenRouterTransport, _BaseEnrichmentClient):
    def __init__(self, settings: OpenRouterSettings | None = None):
        self.settings = settings or OpenRouterSettings.from_env()
        OpenRouterTransport.__init__(self, self.settings)


class InceptionClient(InceptionTransport, _BaseEnrichmentClient):
    def __init__(self, settings: InceptionSettings | None = None):
        self.settings = settings or InceptionSettings.from_env()
        InceptionTransport.__init__(self, self.settings)


def build_enrichment_client_from_env() -> ModuleEnrichmentProvider:
    settings = get_provider_settings_from_env()
    provider_name = settings.provider_name.strip().lower()
    if provider_name == 'openrouter':
        return OpenRouterClient(settings)
    if provider_name in {'inception', 'mercury', 'mercury-2'}:
        return InceptionClient(settings)
    return OpenAICompatibleEnrichmentClient(settings)
