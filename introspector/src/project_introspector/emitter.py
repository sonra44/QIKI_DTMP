from __future__ import annotations

import atexit
import logging
import threading
from time import monotonic
from typing import Any

import httpx

from .models import RuntimeEvent

logger = logging.getLogger(__name__)


class EventEmitter:
    def __init__(
        self,
        endpoint: str,
        project_name: str,
        batch_size: int = 20,
        timeout_seconds: float = 2.0,
        fail_open: bool = True,
        max_buffer_size: int = 1000,
        register_atexit: bool = True,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.project_name = project_name
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds
        self.fail_open = fail_open
        self.max_buffer_size = max_buffer_size
        self._buffer: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._dropped_events_count = 0
        self._flush_failures_count = 0
        self._last_drop_warning_at = 0.0
        if register_atexit:
            atexit.register(self._flush_at_exit)

    def _build_client(self) -> httpx.Client:
        timeout = httpx.Timeout(
            connect=min(self.timeout_seconds, 2.0),
            read=self.timeout_seconds,
            write=self.timeout_seconds,
            pool=min(self.timeout_seconds, 2.0),
        )
        transport = httpx.HTTPTransport(retries=1)
        return httpx.Client(timeout=timeout, transport=transport)

    @property
    def buffer_size(self) -> int:
        with self._lock:
            return len(self._buffer)

    @property
    def dropped_events_count(self) -> int:
        with self._lock:
            return self._dropped_events_count

    @property
    def flush_failures_count(self) -> int:
        with self._lock:
            return self._flush_failures_count

    def health(self) -> dict[str, object]:
        with self._lock:
            return {
                "buffer_size": len(self._buffer),
                "max_buffer_size": self.max_buffer_size,
                "dropped_events_count": self._dropped_events_count,
                "flush_failures_count": self._flush_failures_count,
                "fail_open": self.fail_open,
                "endpoint": self.endpoint,
            }

    def emit(self, event: RuntimeEvent) -> None:
        payload = event.model_dump(mode="json")
        should_flush = False
        with self._lock:
            self._buffer.append(payload)
            self._trim_buffer_locked()
            should_flush = len(self._buffer) >= self.batch_size
        if should_flush:
            self.flush(suppress_errors=self.fail_open)

    def flush(self, *, suppress_errors: bool | None = None) -> int:
        suppress_errors = self.fail_open if suppress_errors is None else suppress_errors
        with self._lock:
            if not self._buffer:
                return 0
            batch = list(self._buffer)
            self._buffer.clear()

        try:
            with self._build_client() as client:
                response = client.post(self.endpoint, json=batch)
                response.raise_for_status()
            return len(batch)
        except Exception:
            with self._lock:
                self._flush_failures_count += 1
                self._buffer = batch + self._buffer
                self._trim_buffer_locked()
            if suppress_errors:
                logger.warning("project-introspector runtime flush failed", exc_info=True)
                return 0
            raise

    def _flush_at_exit(self) -> None:
        try:
            self.flush(suppress_errors=True)
        except Exception:
            logger.debug("project-introspector exit flush failed", exc_info=True)

    def _trim_buffer_locked(self) -> None:
        if self.max_buffer_size <= 0:
            return
        overflow = len(self._buffer) - self.max_buffer_size
        if overflow > 0:
            del self._buffer[:overflow]
            self._dropped_events_count += overflow
            now = monotonic()
            if now - self._last_drop_warning_at >= 5.0:
                logger.warning(
                    "project-introspector runtime buffer dropped %s old event(s) to stay within max_buffer_size=%s",
                    overflow,
                    self.max_buffer_size,
                )
                self._last_drop_warning_at = now
