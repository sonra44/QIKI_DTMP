from __future__ import annotations

import json
import os
import threading
import time
from typing import Optional
from urllib.parse import urlparse
from urllib.request import urlopen

from qiki.services.q_core_agent.core.agent_logger import logger
from qiki.shared.models.core import BiosStatus


def _unavailable_status() -> BiosStatus:
    return BiosStatus(bios_version="unavailable", firmware_version="unavailable", post_results=[])


_DEFAULT_BIOS_BASE_URL = "http://q-bios-service:8080"


def _validated_bios_base_url() -> str:
    raw = os.getenv("BIOS_URL")
    base = (raw if raw is not None else _DEFAULT_BIOS_BASE_URL).strip()
    if not base:
        base = _DEFAULT_BIOS_BASE_URL

    base = base.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"BIOS_URL scheme must be http or https, got: {parsed.scheme!r}")
    if not parsed.netloc:
        raise ValueError("BIOS_URL must include host[:port]")

    return base


def _fetch_bios_status_blocking() -> BiosStatus:
    url = "<unavailable>"
    timeout_s = float(os.getenv("BIOS_HTTP_TIMEOUT_SEC", "2.0"))
    try:
        base = _validated_bios_base_url()
        url = f"{base}/bios/status"
        with urlopen(url, timeout=timeout_s) as resp:
            raw = resp.read()
        payload = json.loads(raw.decode("utf-8"))
        if isinstance(payload, dict):
            return BiosStatus.model_validate(payload)
        raise ValueError("BIOS payload is not a JSON object")
    except Exception as e:
        logger.warning("BIOS unavailable (%s): %s", url, e)
        return _unavailable_status()


class _BiosStatusCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cached: Optional[BiosStatus] = None
        self._in_flight = False
        self._last_attempt_ts = 0.0

    def get(self) -> BiosStatus:
        ttl_s = float(os.getenv("BIOS_CACHE_TTL_SEC", "5.0"))
        if ttl_s <= 0:
            return _fetch_bios_status_blocking()

        now = time.time()
        with self._lock:
            current = self._cached if self._cached is not None else _unavailable_status()
            should_refresh = (not self._in_flight) and (now - self._last_attempt_ts >= ttl_s)
            if should_refresh:
                self._in_flight = True
                self._last_attempt_ts = now
                threading.Thread(target=self._refresh, daemon=True).start()
            return current

    def _refresh(self) -> None:
        try:
            status = _fetch_bios_status_blocking()
        except Exception as exc:  # pragma: no cover
            logger.warning("BIOS background refresh failed: %s", exc)
            status = None
        with self._lock:
            if status is not None:
                self._cached = status
            self._in_flight = False

    def _reset_for_tests(self) -> None:
        with self._lock:
            self._cached = None
            self._in_flight = False
            self._last_attempt_ts = 0.0


_CACHE = _BiosStatusCache()


def fetch_bios_status() -> BiosStatus:
    """Return BIOS status without blocking the agent tick loop.

    Policy:
    - If BIOS_CACHE_TTL_SEC <= 0: do a blocking fetch (legacy behavior).
    - Otherwise: return cached value immediately and refresh in background at most once per TTL.
    """
    return _CACHE.get()
