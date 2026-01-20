from __future__ import annotations

import time

import pytest

from qiki.services.q_core_agent.core import bios_http_client
from qiki.shared.models.core import BiosStatus


def test_fetch_bios_status_cached_returns_immediately_and_refreshes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIOS_CACHE_TTL_SEC", "0.1")
    monkeypatch.setenv("BIOS_URL", "http://example.invalid")
    monkeypatch.setenv("BIOS_HTTP_TIMEOUT_SEC", "2.0")

    bios_http_client._CACHE._reset_for_tests()

    def fake_blocking_fetch() -> BiosStatus:
        return BiosStatus(bios_version="v1", firmware_version="f1", post_results=[])

    monkeypatch.setattr(bios_http_client, "_fetch_bios_status_blocking", fake_blocking_fetch)
    monkeypatch.setattr(bios_http_client.time, "time", lambda: 1000.0)

    # First call: returns immediately (unavailable) but schedules background refresh.
    first = bios_http_client.fetch_bios_status()
    assert first.bios_version in {"unavailable", "v1"}

    # Give the background thread a moment to run.
    time.sleep(0.05)

    # Second call: should now return refreshed value.
    second = bios_http_client.fetch_bios_status()
    assert second.bios_version == "v1"


def test_fetch_bios_status_blocking_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIOS_CACHE_TTL_SEC", "0")
    bios_http_client._CACHE._reset_for_tests()

    def fake_blocking_fetch() -> BiosStatus:
        return BiosStatus(bios_version="v2", firmware_version="f2", post_results=[])

    monkeypatch.setattr(bios_http_client, "_fetch_bios_status_blocking", fake_blocking_fetch)

    status = bios_http_client.fetch_bios_status()
    assert status.bios_version == "v2"


def test_bios_url_empty_string_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIOS_URL", "")

    captured: dict[str, object] = {}

    class _DummyResponse:
        def __enter__(self) -> "_DummyResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        def read(self) -> bytes:
            return b'{"bios_version":"v3","firmware_version":"f3","post_results":[]}'

    def fake_urlopen(url: str, timeout: float) -> _DummyResponse:
        captured["url"] = url
        captured["timeout"] = timeout
        return _DummyResponse()

    monkeypatch.setattr(bios_http_client, "urlopen", fake_urlopen)

    status = bios_http_client._fetch_bios_status_blocking()
    assert status.bios_version == "v3"
    assert captured["url"] == "http://q-bios-service:8080/bios/status"


def test_bios_url_rejects_non_http_scheme_without_urlopen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIOS_URL", "file:///etc/passwd")

    def must_not_be_called(*args: object, **kwargs: object) -> object:
        raise AssertionError("urlopen must not be called for non-http(s) BIOS_URL")

    monkeypatch.setattr(bios_http_client, "urlopen", must_not_be_called)

    status = bios_http_client._fetch_bios_status_blocking()
    assert status.bios_version == "unavailable"
