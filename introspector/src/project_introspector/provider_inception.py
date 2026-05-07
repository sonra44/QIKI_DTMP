from __future__ import annotations

import os

from .provider_openai_compat import OpenAICompatibleSettings, OpenAICompatibleTransport

DEFAULT_INCEPTION_BASE_URL = 'https://api.inceptionlabs.ai/v1'
DEFAULT_INCEPTION_MODEL = 'mercury-2'
DEFAULT_INCEPTION_FALLBACK_MODEL = 'mercury-coder-small-beta'


class InceptionSettings(OpenAICompatibleSettings):
    @classmethod
    def from_env(cls) -> 'InceptionSettings':
        timeout_raw = (
            os.getenv('INTROSPECTOR_TIMEOUT_SECONDS')
            or os.getenv('LLM_PROVIDER_TIMEOUT_SECONDS')
            or os.getenv('INCEPTION_TIMEOUT_SECONDS')
            or '45'
        )
        try:
            timeout_seconds = float(timeout_raw)
        except ValueError:
            timeout_seconds = 45.0
        api_key = (
            os.getenv('INCEPTION_API_KEY')
            or os.getenv('INTROSPECTOR_API_KEY')
            or os.getenv('LLM_PROVIDER_API_KEY')
        )
        base_url = (
            os.getenv('INTROSPECTOR_BASE_URL')
            or os.getenv('LLM_PROVIDER_BASE_URL')
            or os.getenv('INCEPTION_BASE_URL')
            or DEFAULT_INCEPTION_BASE_URL
        ).rstrip('/')
        default_model = (
            os.getenv('INTROSPECTOR_MODEL')
            or os.getenv('LLM_PROVIDER_MODEL')
            or os.getenv('INCEPTION_MODEL')
            or DEFAULT_INCEPTION_MODEL
        )
        fallback_model = (
            os.getenv('INTROSPECTOR_FALLBACK_MODEL')
            or os.getenv('LLM_PROVIDER_FALLBACK_MODEL')
            or os.getenv('INCEPTION_FALLBACK_MODEL')
            or DEFAULT_INCEPTION_FALLBACK_MODEL
        )
        app_name = (
            os.getenv('INTROSPECTOR_APP_NAME')
            or os.getenv('LLM_PROVIDER_APP_NAME')
            or os.getenv('INCEPTION_APP_NAME')
            or 'project-introspector'
        )
        referer = (
            os.getenv('INTROSPECTOR_HTTP_REFERER')
            or os.getenv('LLM_PROVIDER_HTTP_REFERER')
            or os.getenv('INCEPTION_HTTP_REFERER')
            or os.getenv('INTROSPECTOR_REFERER')
            or os.getenv('LLM_PROVIDER_REFERER')
            or os.getenv('INCEPTION_REFERER')
        )
        provider_name = (
            os.getenv('INTROSPECTOR_PROVIDER')
            or os.getenv('LLM_PROVIDER_NAME')
            or os.getenv('INCEPTION_PROVIDER_NAME')
            or 'inception'
        )
        return cls(
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            fallback_model=fallback_model,
            app_name=app_name,
            referer=referer,
            timeout_seconds=timeout_seconds,
            provider_name=provider_name,
        )


class InceptionTransport(OpenAICompatibleTransport):
    pass
