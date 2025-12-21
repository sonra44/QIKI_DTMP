from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from qiki.shared.events.cloudevents import build_cloudevent_headers
from qiki.shared.nats_subjects import SYSTEM_TELEMETRY

try:
    import nats
except Exception:  # pragma: no cover
    nats = None

logger = logging.getLogger(__name__)


def _rfc3339_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TelemetryNatsPublisher:
    """Best-effort NATS publisher for telemetry snapshots (core NATS, not JetStream)."""

    def __init__(self, nats_url: str, *, subject: str = SYSTEM_TELEMETRY) -> None:
        self._nats_url = nats_url
        self._subject = subject
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._nc: Optional[nats.NATS] = None
        self._thread: Optional[threading.Thread] = None

    def _ensure_loop(self) -> None:
        if self._loop is not None:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    async def _async_connect(self) -> None:
        if nats is None:  # pragma: no cover
            return
        if self._nc is not None:
            return
        try:
            self._nc = await nats.connect(self._nats_url)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to connect to NATS %s: %s", self._nats_url, exc)

    def _ensure_connection(self) -> None:
        self._ensure_loop()
        assert self._loop is not None
        fut = asyncio.run_coroutine_threadsafe(self._async_connect(), self._loop)
        try:
            fut.result(timeout=2.0)
        except Exception as exc:  # pragma: no cover
            logger.debug("NATS connect result: %s", exc)

    async def _async_publish(self, data: bytes, headers: dict[str, str]) -> None:
        if self._nc is None:
            return
        try:
            await self._nc.publish(self._subject, data, headers=headers)
        except Exception as exc:  # pragma: no cover
            logger.debug("NATS publish failed: %s", exc)

    def publish_snapshot(self, payload: dict) -> None:
        """Publish a single telemetry snapshot (best-effort; drops if not connected)."""
        self._ensure_connection()
        if self._loop is None or self._nc is None:
            return

        ts = _rfc3339_utc_now()
        event_id = f"telemetry-{int(ts.timestamp() * 1000)}"
        headers = build_cloudevent_headers(
            event_id=event_id,
            event_type="qiki.telemetry.v1.Snapshot",
            source="urn:qiki:q-sim-service:telemetry",
            event_time=ts,
        )
        headers["Nats-Msg-Id"] = event_id

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        asyncio.run_coroutine_threadsafe(self._async_publish(data, headers), self._loop)
