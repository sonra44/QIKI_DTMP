from __future__ import annotations

import httpx
import pytest

from project_introspector.provider_errors import ProviderCallError, ProviderErrorKind, kind_from_status_code
from project_introspector.provider_openai_compat import OpenAICompatibleSettings, OpenAICompatibleTransport


def _settings() -> OpenAICompatibleSettings:
    return OpenAICompatibleSettings(
        api_key="secret",
        base_url="https://provider.example/v1",
        default_model="demo-model",
        provider_name="demo-provider",
        timeout_seconds=0.1,
    )


def _transport_for(handler):
    transport = OpenAICompatibleTransport(_settings())
    transport._build_client = lambda: httpx.Client(transport=httpx.MockTransport(handler))  # type: ignore[method-assign]
    return transport


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, ProviderErrorKind.AUTH_ERROR),
        (403, ProviderErrorKind.AUTH_ERROR),
        (429, ProviderErrorKind.RATE_LIMITED),
        (500, ProviderErrorKind.SERVER_ERROR),
        (502, ProviderErrorKind.SERVER_ERROR),
        (503, ProviderErrorKind.SERVER_ERROR),
    ],
)
def test_provider_http_statuses_are_classified_without_fallback(status_code: int, expected: ProviderErrorKind) -> None:
    assert kind_from_status_code(status_code) == expected

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "boom"})

    transport = _transport_for(handler)

    with pytest.raises(ProviderCallError) as exc_info:
        transport._best_effort_chat(
            selected_model="demo-model",
            temperature=0.0,
            messages=[{"role": "user", "content": "{}"}],
            schema_name="demo",
            schema={"type": "object", "properties": {}, "additionalProperties": True},
        )

    assert exc_info.value.kind == expected
    assert exc_info.value.status_code == status_code
    assert exc_info.value.retryable is (expected in {ProviderErrorKind.RATE_LIMITED, ProviderErrorKind.SERVER_ERROR})


def test_provider_timeout_is_classified() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    transport = _transport_for(handler)

    with pytest.raises(ProviderCallError) as exc_info:
        transport._post_chat({"model": "demo-model", "messages": []}, structured_output_used=False)

    assert exc_info.value.kind == ProviderErrorKind.TIMEOUT
    assert exc_info.value.retryable is True


def test_provider_network_error_is_classified() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    transport = _transport_for(handler)

    with pytest.raises(ProviderCallError) as exc_info:
        transport._post_chat({"model": "demo-model", "messages": []}, structured_output_used=False)

    assert exc_info.value.kind == ProviderErrorKind.NETWORK_ERROR
    assert exc_info.value.retryable is True


def test_provider_malformed_response_is_bad_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    transport = _transport_for(handler)

    with pytest.raises(ProviderCallError) as exc_info:
        transport._post_chat({"model": "demo-model", "messages": []}, structured_output_used=False)

    assert exc_info.value.kind == ProviderErrorKind.BAD_RESPONSE


def test_structured_output_bad_request_falls_back_to_unstructured() -> None:
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content.decode("utf-8"))
        calls.append(payload)
        if "response_format" in payload:
            return httpx.Response(400, json={"error": "schema unsupported"})
        return httpx.Response(
            200,
            json={
                "model": "provider-demo-model",
                "choices": [{"message": {"content": "{\"status\": \"ok\"}"}}],
            },
        )

    transport = _transport_for(handler)
    parsed, raw = transport._best_effort_chat(
        selected_model="demo-model",
        temperature=0.0,
        messages=[{"role": "user", "content": "{}"}],
        schema_name="demo",
        schema={"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]},
    )

    assert parsed == {"status": "ok"}
    assert raw == "{\"status\": \"ok\"}"
    assert len(calls) == 2
    assert transport.last_call_metadata is not None
    assert transport.last_call_metadata.structured_output_used is False
    assert transport.last_call_metadata.structured_output_fallback is True
    assert transport.last_call_metadata.provider_model_used == "provider-demo-model"
