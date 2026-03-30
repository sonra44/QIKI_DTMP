"""
NATS Client for Operator Console.

Handles connection to NATS JetStream and subscribes to telemetry streams.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

import nats
from nats.js import JetStreamContext
from nats.errors import TimeoutError, NoServersError

from qiki.shared.nats_subjects import (
    EVENTS_STREAM_NAME,
    OPERATOR_CONSOLE_RADAR_LR_DURABLE,
    OPERATOR_CONSOLE_RADAR_SR_DURABLE,
    OPERATOR_CONSOLE_TRACKS_DURABLE,
    EVENTS_V1_WILDCARD,
    RADAR_FRAMES_LR,
    RADAR_TRACKS,
    RADAR_TRACKS_SR,
    SYSTEM_TELEMETRY,
    RESPONSES_CONTROL,
    QIKI_RESPONSES,
)

logger = logging.getLogger(__name__)


async def _safe_ack(msg: Any, *, context: str) -> None:
    try:
        await msg.ack()
    except Exception:
        logger.debug("operator_nats_ack_failed context=%s", context, exc_info=True)


def _message_timestamp_seconds(msg: Any) -> float | None:
    metadata = getattr(msg, "metadata", None)
    stamp = getattr(metadata, "timestamp", None)
    if stamp is None:
        return None
    if isinstance(stamp, datetime):
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.timestamp()
    try:
        return float(stamp)
    except (TypeError, ValueError):
        return None


class NATSClient:
    """Async NATS client for telemetry subscription."""

    def __init__(self, url: Optional[str] = None):
        """
        Initialize NATS client.

        Args:
            url: NATS server URL, defaults to env var NATS_URL
        """
        env_url = os.getenv("NATS_URL", "nats://localhost:4222") or "nats://localhost:4222"
        self.url: str = url if url is not None else env_url
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[JetStreamContext] = None
        self.subscriptions: Dict[str, Any] = {}
        self.callbacks: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._subscription_factories: Dict[str, Callable[[], Awaitable[Any]]] = {}
        self._resubscribe_lock = asyncio.Lock()
        self._lifecycle_callback: Callable[[str], Awaitable[None]] | None = None
        self._connection_state = "lost"
        self.decode_errors_control_responses: int = 0
        self.decode_errors_qiki_responses: int = 0
        self._decode_error_log_period_s: float = 10.0
        self._decode_error_last_log_ts: dict[str, float] = {}

    @property
    def connection_state(self) -> str:
        return self._connection_state

    @property
    def active_subscriptions(self) -> int:
        return len(self.subscriptions)

    def set_lifecycle_callback(self, callback: Callable[[str], Awaitable[None]] | None) -> None:
        self._lifecycle_callback = callback

    async def connect(self) -> None:
        """Connect to NATS server and initialize JetStream."""

        async def _emit_state(state: str) -> None:
            self._connection_state = state
            if self._lifecycle_callback is not None:
                try:
                    await self._lifecycle_callback(state)
                except Exception:
                    logger.debug("operator_nats_lifecycle_callback_failed", exc_info=True)

        async def _disconnected_cb() -> None:
            await _emit_state("reconnecting")

        async def _reconnected_cb() -> None:
            await _emit_state("connected")
            await self._resubscribe_all()

        async def _closed_cb() -> None:
            await _emit_state("lost")

        try:
            self.nc = await nats.connect(
                servers=[self.url],
                connect_timeout=5,
                reconnect_time_wait=1,
                max_reconnect_attempts=-1,
                disconnected_cb=_disconnected_cb,
                reconnected_cb=_reconnected_cb,
                closed_cb=_closed_cb,
            )
            self.js = self.nc.jetstream()
            await _emit_state("connected")
        except (NoServersError, TimeoutError):
            self._connection_state = "lost"
            raise

    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self.nc:
            await self.nc.drain()
            await self.nc.close()
        self._connection_state = "lost"

    async def subscribe_radar_sr(self, callback: Callable[[Dict], Awaitable[None]]) -> None:
        """
        Subscribe to short-range radar stream.

        Args:
            callback: Function to call with radar data
        """
        if not self.js:
            raise RuntimeError("Not connected to JetStream")

        self.callbacks["RADAR_SR"] = callback

        async def message_handler(msg):
            """Handle incoming radar messages."""
            try:
                data = json.loads(msg.data.decode())
                await callback({"stream": "RADAR_SR", "timestamp": datetime.now().isoformat(), "data": data})
                await _safe_ack(msg, context="RADAR_SR")
            except Exception:
                logger.debug("operator_nats_message_handler_failed stream=RADAR_SR", exc_info=True)
                await _safe_ack(msg, context="RADAR_SR")

        async def _factory() -> Any:
            if not self.js:
                raise RuntimeError("Not connected to JetStream")
            subject = os.getenv("RADAR_SR_SUBJECT", RADAR_TRACKS_SR)
            return await self.js.subscribe(
                subject, cb=message_handler, durable=OPERATOR_CONSOLE_RADAR_SR_DURABLE, manual_ack=True
            )

        await self._register_subscription("RADAR_SR", _factory)

    async def subscribe_radar_lr(self, callback: Callable[[Dict], Awaitable[None]]) -> None:
        """
        Subscribe to long-range radar stream.

        Args:
            callback: Function to call with radar data
        """
        if not self.js:
            raise RuntimeError("Not connected to JetStream")

        self.callbacks["RADAR_LR"] = callback

        async def message_handler(msg):
            """Handle incoming radar messages."""
            try:
                data = json.loads(msg.data.decode())
                await callback({"stream": "RADAR_LR", "timestamp": datetime.now().isoformat(), "data": data})
                await _safe_ack(msg, context="RADAR_LR")
            except Exception:
                logger.debug("operator_nats_message_handler_failed stream=RADAR_LR", exc_info=True)
                await _safe_ack(msg, context="RADAR_LR")

        async def _factory() -> Any:
            if not self.js:
                raise RuntimeError("Not connected to JetStream")
            subject = os.getenv("RADAR_LR_SUBJECT", RADAR_FRAMES_LR)
            return await self.js.subscribe(
                subject, cb=message_handler, durable=OPERATOR_CONSOLE_RADAR_LR_DURABLE, manual_ack=True
            )

        await self._register_subscription("RADAR_LR", _factory)

    async def subscribe_tracks(self, callback: Callable[[Dict], Awaitable[None]]) -> None:
        """
        Subscribe to radar tracks stream.

        Args:
            callback: Function to call with track data
        """
        if not self.js:
            raise RuntimeError("Not connected to JetStream")

        self.callbacks["TRACKS"] = callback

        async def message_handler(msg):
            """Handle incoming track messages."""
            try:
                data = json.loads(msg.data.decode())
                await callback({"stream": "TRACKS", "timestamp": datetime.now().isoformat(), "data": data})
                await _safe_ack(msg, context="TRACKS")
            except Exception:
                logger.debug("operator_nats_message_handler_failed stream=TRACKS", exc_info=True)
                await _safe_ack(msg, context="TRACKS")

        async def _factory() -> Any:
            if not self.js:
                raise RuntimeError("Not connected to JetStream")
            subject = os.getenv("RADAR_TRACKS_SUBJECT", RADAR_TRACKS)
            durable = str(os.getenv("RADAR_TRACKS_DURABLE", OPERATOR_CONSOLE_TRACKS_DURABLE) or "").strip()
            subscribe_kwargs: dict[str, Any] = {
                "cb": message_handler,
                "manual_ack": True,
            }
            if durable:
                subscribe_kwargs["durable"] = durable
            return await self.js.subscribe(subject, **subscribe_kwargs)

        await self._register_subscription("TRACKS", _factory)

    async def subscribe_system_telemetry(
        self,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Subscribe to system telemetry (core NATS, not JetStream by default)."""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        async def message_handler(msg):
            try:
                data = json.loads(msg.data.decode())
                await callback(
                    {
                        "stream": "SYSTEM_TELEMETRY",
                        "timestamp": datetime.now().isoformat(),
                        "data": data,
                    }
                )
            except Exception:
                logger.debug("operator_nats_message_handler_failed stream=SYSTEM_TELEMETRY", exc_info=True)
                return

        async def _factory() -> Any:
            if not self.nc:
                raise RuntimeError("Not connected to NATS")
            subject = os.getenv("SYSTEM_TELEMETRY_SUBJECT", SYSTEM_TELEMETRY)
            return await self.nc.subscribe(subject, cb=message_handler)

        await self._register_subscription("SYSTEM_TELEMETRY", _factory)

    async def subscribe_events(
        self,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Subscribe to system events wildcard (core NATS)."""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        async def message_handler(msg):
            try:
                data = json.loads(msg.data.decode())
                await callback(
                    {
                        "stream": "EVENTS",
                        "timestamp": datetime.now().isoformat(),
                        "subject": getattr(msg, "subject", None),
                        "data": data,
                    }
                )
            except Exception:
                logger.debug("operator_nats_message_handler_failed stream=EVENTS", exc_info=True)
                return

        async def _factory() -> Any:
            if not self.nc:
                raise RuntimeError("Not connected to NATS")
            subject = os.getenv("EVENTS_SUBJECT", EVENTS_V1_WILDCARD)
            return await self.nc.subscribe(subject, cb=message_handler)

        await self._register_subscription("EVENTS", _factory)

    async def publish_command(self, subject: str, command: Dict[str, Any]) -> None:
        """
        Publish command to NATS.

        Args:
            subject: NATS subject to publish to
            command: Command data to publish
        """
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        try:
            # `command` can include UUID/datetime values from Pydantic models.
            payload = json.dumps(command, default=str).encode()
            await self.nc.publish(subject, payload)
        except Exception:
            raise

    async def subscribe_control_responses(
        self,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Subscribe to control responses emitted by FastStream bridge."""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        async def message_handler(msg):
            decoded = self._decode_response_message(msg=msg, kind="control_responses")
            if decoded is None:
                return
            await callback(decoded)

        async def _factory() -> Any:
            if not self.nc:
                raise RuntimeError("Not connected to NATS")
            subject = os.getenv("RESPONSES_CONTROL_SUBJECT", RESPONSES_CONTROL)
            return await self.nc.subscribe(subject, cb=message_handler)

        await self._register_subscription("CONTROL_RESPONSES", _factory)

    async def subscribe_qiki_responses(
        self,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Subscribe to QIKI responses (intent reply/proposals)."""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        async def message_handler(msg):
            decoded = self._decode_response_message(msg=msg, kind="qiki_responses")
            if decoded is None:
                return
            await callback(decoded)

        async def _factory() -> Any:
            if not self.nc:
                raise RuntimeError("Not connected to NATS")
            subject = os.getenv("QIKI_RESPONSES_SUBJECT", QIKI_RESPONSES)
            return await self.nc.subscribe(subject, cb=message_handler)

        await self._register_subscription("QIKI_RESPONSES", _factory)

    async def _register_subscription(self, key: str, factory: Callable[[], Awaitable[Any]]) -> None:
        self._subscription_factories[key] = factory
        await self._replace_subscription(key, factory)

    def _decode_response_message(self, *, msg: Any, kind: str) -> dict[str, Any] | None:
        stream = "CONTROL_RESPONSES" if kind == "control_responses" else "QIKI_RESPONSES"
        try:
            data = json.loads(msg.data.decode())
        except Exception as exc:
            self._record_decode_error(kind=kind)
            self._log_decode_error(subject=getattr(msg, "subject", None), exc=exc, payload=msg.data, kind=kind)
            return None
        return {
            "stream": stream,
            "timestamp": datetime.now().isoformat(),
            "subject": getattr(msg, "subject", None),
            "data": data,
        }

    def _record_decode_error(self, *, kind: str) -> None:
        if kind == "control_responses":
            self.decode_errors_control_responses += 1
            return
        if kind == "qiki_responses":
            self.decode_errors_qiki_responses += 1

    def _log_decode_error(self, *, subject: str | None, exc: Exception, payload: bytes, kind: str) -> None:
        now = time.monotonic()
        last = self._decode_error_last_log_ts.get(kind)
        if last is not None and (now - last) < self._decode_error_log_period_s:
            return
        self._decode_error_last_log_ts[kind] = now
        payload_head = payload[:64].hex()
        logger.warning(
            "NATS decode error (%s): subject=%s len=%d err=%s(%s) head=%s",
            kind,
            subject,
            len(payload),
            type(exc).__name__,
            exc,
            payload_head,
        )

    async def _replace_subscription(self, key: str, factory: Callable[[], Awaitable[Any]]) -> None:
        existing = self.subscriptions.get(key)
        if existing is not None:
            try:
                await existing.unsubscribe()
            except Exception:
                logger.debug("operator_nats_unsubscribe_failed key=%s", key, exc_info=True)
        sub = await factory()
        self.subscriptions[key] = sub

    async def _resubscribe_all(self) -> None:
        async with self._resubscribe_lock:
            for key, factory in list(self._subscription_factories.items()):
                try:
                    await self._replace_subscription(key, factory)
                except Exception:
                    logger.debug("operator_nats_resubscribe_failed key=%s", key, exc_info=True)

    async def get_jetstream_info(self) -> Dict[str, Any]:
        """Get JetStream account info."""
        if not self.js:
            raise RuntimeError("Not connected to JetStream")

        try:
            info = await self.js.account_info()
            return {
                "memory": info.memory,
                "storage": info.storage,
                "streams": info.streams,
                "consumers": info.consumers,
            }
        except Exception:
            return {}

    async def fetch_events_history(self, *, limit: int = 200) -> list[dict[str, Any]]:
        """Best-effort fetch of recent events from JetStream events stream."""
        if not self.js:
            return []

        sub = None
        batch = max(1, min(int(limit), 500))
        try:
            sub = await self.js.pull_subscribe(EVENTS_V1_WILDCARD, stream=EVENTS_STREAM_NAME)
            msgs = await sub.fetch(batch=batch, timeout=1)
            history: list[dict[str, Any]] = []
            for msg in msgs:
                try:
                    data = json.loads(msg.data.decode())
                    msg_ts = _message_timestamp_seconds(msg)
                    history.append(
                        {
                            "stream": "EVENTS_REPLAY",
                            "timestamp": msg_ts,
                            "subject": getattr(msg, "subject", None),
                            "data": data,
                        }
                    )
                except Exception:
                    logger.debug("operator_nats_history_decode_failed", exc_info=True)
                finally:
                    await _safe_ack(msg, context="EVENTS_REPLAY")
            return history
        except Exception:
            logger.debug("operator_nats_history_fetch_failed", exc_info=True)
            return []
        finally:
            if sub is not None:
                try:
                    await sub.unsubscribe()
                except Exception:
                    logger.debug("operator_nats_history_unsubscribe_failed", exc_info=True)

    async def fetch_last_event_json(self, *, stream: str, subject: str) -> Dict[str, Any] | None:
        """Fetch the last JetStream message for a subject and decode JSON.

        This is used for boot-time hydration of operator UI state (no mocks): for example, to
        render the last-known system mode even if the core-NATS event was published before
        ORION subscribed.
        """
        if not self.js:
            raise RuntimeError("Not connected to JetStream")
        msg = await self.js.get_last_msg(stream, subject)
        raw = msg.data
        if raw is None:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return None
        return data if isinstance(data, dict) else None


# Example usage for testing
async def test_client():
    """Test NATS client functionality."""
    client = NATSClient()

    async def radar_callback(data):
        print(f"Received radar data: {data}")

    async def track_callback(data):
        print(f"Received track data: {data}")

    try:
        await client.connect()

        # Get JetStream info
        info = await client.get_jetstream_info()
        print(f"JetStream info: {info}")

        # Subscribe to streams
        await client.subscribe_radar_sr(radar_callback)
        await client.subscribe_tracks(track_callback)

        # Keep running for a while
        await asyncio.sleep(10)

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_client())
