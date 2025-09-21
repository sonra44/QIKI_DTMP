from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Optional

try:
    import nats  # type: ignore
except Exception:  # pragma: no cover
    nats = None  # type: ignore

from qiki.shared.events import build_cloudevent_headers
from qiki.shared.models.radar import RadarTrackModel


logger = logging.getLogger(__name__)


class RadarTrackPublisher:
    """Publishes `RadarTrackModel` messages to NATS with CloudEvent headers."""

    def __init__(self, nats_url: str, subject: str = "qiki.radar.v1.tracks") -> None:
        self._nats_url = nats_url
        self._subject = subject
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._nc: Optional["nats.NATS"] = None  # type: ignore
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def build_payload(track: RadarTrackModel) -> bytes:
        payload = track.model_dump(mode="json")
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def build_headers(track: RadarTrackModel) -> dict[str, str]:
        headers = build_cloudevent_headers(
            event_id=str(track.track_id),
            event_type="qiki.radar.v1.Track",
            source="urn:qiki:faststream-bridge:radar",  # stable source identifier
            event_time=track.timestamp,
        )
        headers["Nats-Msg-Id"] = str(track.track_id)
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

    async def _async_publish(self, data: bytes, headers: dict[str, str]) -> None:
        if self._nc is None:
            return
        try:
            await self._nc.publish(self._subject, data, headers=headers)
        except Exception as exc:  # pragma: no cover
            logger.debug("NATS publish failed: %s", exc)

    def publish_track(self, track: RadarTrackModel) -> None:
        self._ensure_connection()
        if self._loop is None or self._nc is None:
            return
        data = self.build_payload(track)
        headers = self.build_headers(track)
        asyncio.run_coroutine_threadsafe(self._async_publish(data, headers), self._loop)
