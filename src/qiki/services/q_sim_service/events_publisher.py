import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from qiki.shared.events.cloudevents import build_cloudevent_headers

try:
    import nats
except Exception:  # pragma: no cover
    nats = None

logger = logging.getLogger(__name__)


def _rfc3339_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SimEventsNatsPublisher:
    """Best-effort NATS publisher for simulation events (core NATS, not JetStream)."""

    def __init__(self, nats_url: str) -> None:
        self._nats_url = nats_url
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

    async def _async_publish(self, subject: str, data: bytes, headers: dict[str, str]) -> None:
        if self._nc is None:
            return
        try:
            await self._nc.publish(subject, data, headers=headers)
        except Exception as exc:  # pragma: no cover
            logger.debug("NATS publish failed: %s", exc)

    def publish_event(self, subject: str, payload: dict, *, event_type: str, source: str) -> None:
        """Publish a single event payload to any subject (best-effort; drops if not connected)."""
        self._ensure_connection()
        if self._loop is None or self._nc is None:
            return

        ts = _rfc3339_utc_now()
        event_id = f"evt-{int(ts.timestamp() * 1000)}-{uuid4().hex}"
        headers = build_cloudevent_headers(
            event_id=event_id,
            event_type=event_type,
            source=source,
            event_time=ts,
        )
        headers["Nats-Msg-Id"] = event_id

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        asyncio.run_coroutine_threadsafe(self._async_publish(subject, data, headers), self._loop)
