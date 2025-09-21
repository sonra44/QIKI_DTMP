from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Optional

from qiki.shared.events import build_cloudevent_headers

try:
    # Optional dependency; imported lazily in _ensure_connection as well
    import nats  # type: ignore
except Exception:  # pragma: no cover - optional, handled at runtime
    nats = None  # type: ignore

from qiki.shared.models.radar import RadarFrameModel


logger = logging.getLogger(__name__)


class RadarNatsPublisher:
    """Minimal NATS publisher for RadarFrame messages.

    - Optional: works only when RADAR_NATS_ENABLED=true and nats-py is available.
    - Runs a dedicated asyncio loop in a background thread to avoid blocking QSim main loop.
    """

    def __init__(self, nats_url: str, subject: str = "qiki.radar.v1.frames") -> None:
        self._nats_url = nats_url
        self._subject = subject
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._nc: Optional["nats.NATS"] = None  # type: ignore
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def build_payload(frame: RadarFrameModel) -> bytes:
        """Serialize RadarFrameModel to JSON bytes (UTF-8)."""
        # Use JSON mode to convert UUID/datetime to JSON-friendly values
        payload = frame.model_dump(mode="json")
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def build_headers(frame: RadarFrameModel) -> dict:
        """Build NATS headers enabling JetStream deduplication and CloudEvents."""

        headers = build_cloudevent_headers(
            event_id=str(frame.frame_id),
            event_type="qiki.radar.v1.Frame",
            source="urn:qiki:q-sim-service:radar",  # stable identifier
            event_time=frame.timestamp,
        )
        headers["Nats-Msg-Id"] = str(frame.frame_id)
        return headers

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
        if self._nc is None:
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

    async def _async_publish(self, data: bytes, headers: dict | None = None) -> None:
        if self._nc is None:
            return
        try:
            if headers:
                await self._nc.publish(self._subject, data, headers=headers)
            else:
                await self._nc.publish(self._subject, data)
        except Exception as exc:  # pragma: no cover
            logger.debug("NATS publish failed: %s", exc)

    def publish_frame(self, frame: RadarFrameModel) -> None:
        """Serialize and publish frame, if connection available.

        Non-blocking; silently no-ops if NATS client is unavailable.
        """
        self._ensure_connection()
        if self._loop is None or self._nc is None:
            return
        data = self.build_payload(frame)
        headers = self.build_headers(frame)
        asyncio.run_coroutine_threadsafe(self._async_publish(data, headers=headers), self._loop)
