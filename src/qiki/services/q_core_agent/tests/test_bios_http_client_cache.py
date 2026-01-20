from __future__ import annotations

import os
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

