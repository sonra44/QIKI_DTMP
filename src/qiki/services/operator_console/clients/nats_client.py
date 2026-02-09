"""
NATS Client for Operator Console.

Handles connection to NATS JetStream and subscribes to telemetry streams.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

import nats
from nats.js import JetStreamContext
from nats.errors import TimeoutError, NoServersError

from qiki.shared.nats_subjects import (
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

    async def connect(self) -> None:
        """Connect to NATS server and initialize JetStream."""
        try:
            self.nc = await nats.connect(
                servers=[self.url],
                connect_timeout=5,
                reconnect_time_wait=1,
                max_reconnect_attempts=-1,
            )
            self.js = self.nc.jetstream()
        except (NoServersError, TimeoutError):
            raise

    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self.nc:
            await self.nc.drain()
            await self.nc.close()

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

        # Subscribe to the stream
        try:
            subject = os.getenv("RADAR_SR_SUBJECT", RADAR_TRACKS_SR)
            sub = await self.js.subscribe(
                subject, cb=message_handler, durable=OPERATOR_CONSOLE_RADAR_SR_DURABLE, manual_ack=True
            )
            self.subscriptions["RADAR_SR"] = sub
        except Exception:
            raise

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

        # Subscribe to the stream
        try:
            subject = os.getenv("RADAR_LR_SUBJECT", RADAR_FRAMES_LR)
            sub = await self.js.subscribe(
                subject, cb=message_handler, durable=OPERATOR_CONSOLE_RADAR_LR_DURABLE, manual_ack=True
            )
            self.subscriptions["RADAR_LR"] = sub
        except Exception:
            raise

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

        # Subscribe to the stream
        try:
            subject = os.getenv("RADAR_TRACKS_SUBJECT", RADAR_TRACKS)
            sub = await self.js.subscribe(
                subject, cb=message_handler, durable=OPERATOR_CONSOLE_TRACKS_DURABLE, manual_ack=True
            )
            self.subscriptions["TRACKS"] = sub
        except Exception:
            raise

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

        subject = os.getenv("SYSTEM_TELEMETRY_SUBJECT", SYSTEM_TELEMETRY)
        try:
            sub = await self.nc.subscribe(subject, cb=message_handler)
            self.subscriptions["SYSTEM_TELEMETRY"] = sub
        except Exception:
            raise

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

        subject = os.getenv("EVENTS_SUBJECT", EVENTS_V1_WILDCARD)
        try:
            sub = await self.nc.subscribe(subject, cb=message_handler)
            self.subscriptions["EVENTS"] = sub
        except Exception:
            raise

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
            try:
                data = json.loads(msg.data.decode())
                await callback(
                    {
                        "stream": "CONTROL_RESPONSES",
                        "timestamp": datetime.now().isoformat(),
                        "subject": getattr(msg, "subject", None),
                        "data": data,
                    }
                )
            except Exception:
                return

        subject = os.getenv("RESPONSES_CONTROL_SUBJECT", RESPONSES_CONTROL)
        try:
            sub = await self.nc.subscribe(subject, cb=message_handler)
            self.subscriptions["CONTROL_RESPONSES"] = sub
        except Exception:
            raise

    async def subscribe_qiki_responses(
        self,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Subscribe to QIKI responses (intent reply/proposals)."""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        async def message_handler(msg):
            try:
                data = json.loads(msg.data.decode())
                await callback(
                    {
                        "stream": "QIKI_RESPONSES",
                        "timestamp": datetime.now().isoformat(),
                        "subject": getattr(msg, "subject", None),
                        "data": data,
                    }
                )
            except Exception:
                return

        subject = os.getenv("QIKI_RESPONSES_SUBJECT", QIKI_RESPONSES)
        try:
            sub = await self.nc.subscribe(subject, cb=message_handler)
            self.subscriptions["QIKI_RESPONSES"] = sub
        except Exception:
            raise

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
