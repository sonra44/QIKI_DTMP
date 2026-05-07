from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from .provider_errors import ProviderCallError, ProviderErrorKind, kind_from_status_code


@dataclass(slots=True)
class OpenAICompatibleSettings:
    api_key: str | None
    base_url: str
    default_model: str
    fallback_model: str | None = None
    app_name: str = "project-introspector"
    referer: str | None = None
    timeout_seconds: float = 45.0
    provider_name: str = "openai-compatible"

    @classmethod
    def from_env(
        cls,
        *,
        prefix: str = "LLM_PROVIDER_",
        default_base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4.1-mini",
        default_fallback_model: str | None = None,
        default_app_name: str = "project-introspector",
        default_provider_name: str = "openai-compatible",
        allow_openrouter_aliases: bool = False,
    ) -> "OpenAICompatibleSettings":
        def _get(name: str) -> str | None:
            value = os.getenv(f"{prefix}{name}")
            if value is not None:
                return value
            if allow_openrouter_aliases:
                alias_map = {
                    "API_KEY": "OPENROUTER_API_KEY",
                    "BASE_URL": "OPENROUTER_BASE_URL",
                    "MODEL": "OPENROUTER_MODEL",
                    "FALLBACK_MODEL": "OPENROUTER_FALLBACK_MODEL",
                    "APP_NAME": "OPENROUTER_APP_NAME",
                    "HTTP_REFERER": "OPENROUTER_HTTP_REFERER",
                    "REFERER": "OPENROUTER_REFERER",
                    "TIMEOUT_SECONDS": "OPENROUTER_TIMEOUT_SECONDS",
                    "NAME": None,
                }
                alias = alias_map.get(name)
                if alias:
                    return os.getenv(alias)
            return None

        timeout_raw = _get("TIMEOUT_SECONDS") or "45"
        try:
            timeout_seconds = float(timeout_raw)
        except ValueError:
            timeout_seconds = 45.0
        referer = _get("HTTP_REFERER") or _get("REFERER")
        base_url = (_get("BASE_URL") or default_base_url).rstrip("/")
        return cls(
            api_key=_get("API_KEY"),
            base_url=base_url,
            default_model=_get("MODEL") or default_model,
            fallback_model=_get("FALLBACK_MODEL") or default_fallback_model,
            app_name=_get("APP_NAME") or default_app_name,
            referer=referer,
            timeout_seconds=timeout_seconds,
            provider_name=_get("NAME") or default_provider_name,
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


@dataclass(slots=True)
class ProviderCallMetadata:
    requested_model: str
    provider_model_used: str | None = None
    structured_output_used: bool = False
    structured_output_fallback: bool = False


class OpenAICompatibleTransport:
    def __init__(self, settings: OpenAICompatibleSettings):
        self.settings = settings
        self.last_call_metadata: ProviderCallMetadata | None = None

    def _headers(self) -> dict[str, str]:
        if not self.settings.api_key:
            raise ProviderCallError(
                "Provider API key is not configured",
                kind=ProviderErrorKind.NOT_CONFIGURED,
                provider_name=self.settings.provider_name,
                retryable=False,
            )
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.settings.app_name,
        }
        if self.settings.referer:
            headers["HTTP-Referer"] = self.settings.referer
        return headers

    def _build_client(self) -> httpx.Client:
        timeout = httpx.Timeout(
            connect=min(self.settings.timeout_seconds, 5.0),
            read=self.settings.timeout_seconds,
            write=self.settings.timeout_seconds,
            pool=min(self.settings.timeout_seconds, 5.0),
        )
        transport = httpx.HTTPTransport(retries=1)
        return httpx.Client(timeout=timeout, transport=transport)

    def _chat_url(self) -> str:
        return f"{self.settings.base_url}/chat/completions"

    def _model_selector(self, selected_model: str) -> dict[str, Any]:
        return {"model": selected_model}

    def _structured_payload(
        self,
        *,
        selected_model: str,
        temperature: float,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            **self._model_selector(selected_model),
            "temperature": temperature,
            "stream": False,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }

    def _unstructured_payload(
        self,
        *,
        selected_model: str,
        temperature: float,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        return {
            **self._model_selector(selected_model),
            "temperature": temperature,
            "stream": False,
            "messages": messages,
        }

    def _raise_status(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            kind = kind_from_status_code(status_code)
            raise ProviderCallError(
                f"Provider returned HTTP {status_code}",
                kind=kind,
                status_code=status_code,
                provider_name=self.settings.provider_name,
            ) from exc

    def _post_chat(self, payload: dict[str, Any], *, structured_output_used: bool) -> tuple[dict[str, Any], str]:
        try:
            with self._build_client() as client:
                response = client.post(self._chat_url(), headers=self._headers(), json=payload)
                self._raise_status(response)
                try:
                    body = response.json()
                except ValueError as exc:
                    raise ProviderCallError(
                        "Provider returned non-JSON response",
                        kind=ProviderErrorKind.BAD_RESPONSE,
                        provider_name=self.settings.provider_name,
                    ) from exc
        except ProviderCallError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderCallError(
                f"Provider request timed out: {exc}",
                kind=ProviderErrorKind.TIMEOUT,
                provider_name=self.settings.provider_name,
            ) from exc
        except httpx.TransportError as exc:
            raise ProviderCallError(
                f"Provider network error: {exc}",
                kind=ProviderErrorKind.NETWORK_ERROR,
                provider_name=self.settings.provider_name,
            ) from exc

        content = self._extract_message_content(body)
        provider_model_used = self._extract_provider_model(body)
        requested_model = str(payload.get('model') or (payload.get('models') or [''])[0])
        self.last_call_metadata = ProviderCallMetadata(
            requested_model=requested_model,
            provider_model_used=provider_model_used,
            structured_output_used=structured_output_used,
            structured_output_fallback=False,
        )
        try:
            parsed = self._extract_json(content)
        except (json.JSONDecodeError, ValueError):
            parsed = {"raw_text": content}
        return parsed, content

    def _best_effort_chat(
        self,
        *,
        selected_model: str,
        temperature: float,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        structured_payload = self._structured_payload(
            selected_model=selected_model,
            temperature=temperature,
            messages=messages,
            schema_name=schema_name,
            schema=schema,
        )
        try:
            return self._post_chat(structured_payload, structured_output_used=True)
        except ProviderCallError as exc:
            if exc.kind not in {
                ProviderErrorKind.BAD_REQUEST,
                ProviderErrorKind.NOT_FOUND,
                ProviderErrorKind.UNPROCESSABLE,
            }:
                raise
        except ValueError:
            pass
        parsed, content = self._post_chat(
            self._unstructured_payload(
                selected_model=selected_model,
                temperature=temperature,
                messages=messages,
            ),
            structured_output_used=False,
        )
        if self.last_call_metadata is not None:
            self.last_call_metadata.structured_output_fallback = True
        return parsed, content

    def probe(self, *, model: str | None = None) -> dict[str, object]:
        selected_model = model or self.settings.default_model
        messages = [
            {'role': 'system', 'content': 'Return JSON only.'},
            {'role': 'user', 'content': '{"status":"ok"}'},
        ]
        try:
            parsed, _raw = self._best_effort_chat(
                selected_model=selected_model,
                temperature=0.0,
                messages=messages,
                schema_name='provider_probe',
                schema={
                    'type': 'object',
                    'properties': {'status': {'type': 'string'}},
                    'required': ['status'],
                    'additionalProperties': True,
                },
            )
            metadata = self.last_call_metadata
            return {
                'status': 'ok',
                'configured': self.settings.configured,
                'provider_name': self.settings.provider_name,
                'requested_model': selected_model,
                'provider_model_used': metadata.provider_model_used if metadata else None,
                'structured_output_used': metadata.structured_output_used if metadata else None,
                'structured_output_fallback': metadata.structured_output_fallback if metadata else None,
                'response': parsed,
            }
        except ProviderCallError as exc:
            return {
                'status': 'failed',
                'configured': self.settings.configured,
                'provider_name': self.settings.provider_name,
                'requested_model': selected_model,
                'error_kind': exc.kind.value,
                'status_code': exc.status_code,
                'retryable': exc.retryable,
                'message': exc.message,
            }

    @staticmethod
    def _extract_provider_model(body: dict[str, Any]) -> str | None:
        model = body.get('model')
        if isinstance(model, str):
            return model
        choices = body.get('choices') or []
        if choices and isinstance(choices[0], dict):
            choice_model = choices[0].get('model')
            if isinstance(choice_model, str):
                return choice_model
        return None

    @staticmethod
    def _extract_message_content(body: dict[str, Any]) -> str:
        choices = body.get("choices") or []
        if not choices:
            raise ProviderCallError(
                "Provider response did not contain choices",
                kind=ProviderErrorKind.BAD_RESPONSE,
            )
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
            if text_parts:
                return "\n".join(text_parts)
        raise ProviderCallError(
            "Provider response content was not a text string",
            kind=ProviderErrorKind.BAD_RESPONSE,
        )

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        raw = text.strip()
        if raw.startswith("```"):
            raw = raw.removeprefix("```")
            if raw.startswith("json\n"):
                raw = raw.removeprefix("json\n")
            if raw.endswith("```"):
                raw = raw[: -len("```")]
            raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(raw[start : end + 1])
            raise
