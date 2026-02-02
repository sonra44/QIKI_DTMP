from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from qiki.shared.events import build_cloudevent_headers

try:
    import nats  # type: ignore
except Exception:  # pragma: no cover
    nats = None  # type: ignore

logger = logging.getLogger(__name__)


def _rfc3339_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RadarGuardEventPublisher:
    """Publishes radar guard alert events to NATS (best-effort; drops if not connected)."""

    def __init__(self, nats_url: str, *, subject: str) -> None:
        self._nats_url = nats_url
        self._subject = subject
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._nc: Optional["nats.NATS"] = None  # type: ignore
        self._thread: Optional[threading.Thread] = None

    def _ensure_loop(self) -> None:
        if self._loop is not None:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    async def _async_connect(self) -> None:
        global nats
        if nats is None:
            import importlib

            try:
                nats = importlib.import_module("nats")  # type: ignore
            except Exception as exc:  # pragma: no cover
                logger.warning("nats-py is not available: %s", exc)
                return
        if self._nc is not None:
            return
        try:
            self._nc = await nats.connect(self._nats_url)  # type: ignore
            logger.info("Connected to NATS at %s", self._nats_url)
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

    def publish_guard_alert(self, payload: dict) -> None:
        """
        Publish a single guard alert event payload.

        Payload must already contain the no-mocks event envelope fields used by ORION:
        - schema_version, category, source, subject, ts_epoch, ...
        """
        self._ensure_connection()
        if self._loop is None or self._nc is None:
            return

        now = _rfc3339_utc_now()
        event_id = f"evt-{int(now.timestamp() * 1000)}-{uuid4().hex}"
        headers = build_cloudevent_headers(
            event_id=event_id,
            event_type="qiki.events.v1.RadarGuardAlert",
            source="urn:qiki:faststream-bridge:radar_guard",
            event_time=now,
        )
        headers["Nats-Msg-Id"] = event_id

        # Enforce ts_epoch when missing.
        if "ts_epoch" not in payload:
            payload["ts_epoch"] = float(time.time())

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        asyncio.run_coroutine_threadsafe(self._async_publish(data, headers), self._loop)

