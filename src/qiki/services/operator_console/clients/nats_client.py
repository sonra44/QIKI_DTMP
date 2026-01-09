"""
NATS Client for Operator Console.

Handles connection to NATS JetStream and subscribes to telemetry streams.
"""

import asyncio
import json
import os
from typing import Any, Callable, Dict, Optional, Awaitable
from datetime import datetime

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
    QIKI_PROPOSALS_V1,
)


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
            print(f"✅ Connected to NATS at {self.url}")
        except (NoServersError, TimeoutError) as e:
            print(f"❌ Failed to connect to NATS: {e}")
            raise
            
    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self.nc:
            await self.nc.drain()
            await self.nc.close()
            print("Disconnected from NATS")
            
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
                await callback({
                    "stream": "RADAR_SR",
                    "timestamp": datetime.now().isoformat(),
                    "data": data
                })
                await msg.ack()
            except Exception as e:
                print(f"Error processing RADAR_SR message: {e}")
                
        # Subscribe to the stream
        try:
            subject = os.getenv("RADAR_SR_SUBJECT", RADAR_TRACKS_SR)
            sub = await self.js.subscribe(
                subject,
                cb=message_handler,
                durable=OPERATOR_CONSOLE_RADAR_SR_DURABLE,
                manual_ack=True
            )
            self.subscriptions["RADAR_SR"] = sub
            print(f"✅ Subscribed to RADAR_SR stream: {subject}")
        except Exception as e:
            print(f"❌ Failed to subscribe to RADAR_SR: {e}")
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
                await callback({
                    "stream": "RADAR_LR",
                    "timestamp": datetime.now().isoformat(),
                    "data": data
                })
                await msg.ack()
            except Exception as e:
                print(f"Error processing RADAR_LR message: {e}")
                
        # Subscribe to the stream
        try:
            subject = os.getenv("RADAR_LR_SUBJECT", RADAR_FRAMES_LR)
            sub = await self.js.subscribe(
                subject,
                cb=message_handler,
                durable=OPERATOR_CONSOLE_RADAR_LR_DURABLE,
                manual_ack=True
            )
            self.subscriptions["RADAR_LR"] = sub
            print(f"✅ Subscribed to RADAR_LR stream: {subject}")
        except Exception as e:
            print(f"❌ Failed to subscribe to RADAR_LR: {e}")
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
                await callback({
                    "stream": "TRACKS",
                    "timestamp": datetime.now().isoformat(),
                    "data": data
                })
                await msg.ack()
            except Exception as e:
                print(f"Error processing TRACKS message: {e}")
                
        # Subscribe to the stream
        try:
            subject = os.getenv("RADAR_TRACKS_SUBJECT", RADAR_TRACKS)
            sub = await self.js.subscribe(
                subject,
                cb=message_handler,
                durable=OPERATOR_CONSOLE_TRACKS_DURABLE,
                manual_ack=True
            )
            self.subscriptions["TRACKS"] = sub
            print(f"✅ Subscribed to TRACKS stream: {subject}")
        except Exception as e:
            print(f"❌ Failed to subscribe to TRACKS: {e}")
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
            except Exception as e:
                print(f"Error processing SYSTEM_TELEMETRY message: {e}")

        subject = os.getenv("SYSTEM_TELEMETRY_SUBJECT", SYSTEM_TELEMETRY)
        try:
            sub = await self.nc.subscribe(subject, cb=message_handler)
            self.subscriptions["SYSTEM_TELEMETRY"] = sub
            print(f"✅ Subscribed to SYSTEM_TELEMETRY: {subject}")
        except Exception as e:
            print(f"❌ Failed to subscribe to SYSTEM_TELEMETRY: {e}")
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
            except Exception as e:
                print(f"Error processing EVENTS message: {e}")

        subject = os.getenv("EVENTS_SUBJECT", EVENTS_V1_WILDCARD)
        try:
            sub = await self.nc.subscribe(subject, cb=message_handler)
            self.subscriptions["EVENTS"] = sub
            print(f"✅ Subscribed to EVENTS: {subject}")
        except Exception as e:
            print(f"❌ Failed to subscribe to EVENTS: {e}")
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
            print(f"📤 Published command to {subject}: {command}")
        except Exception as e:
            print(f"❌ Failed to publish command: {e}")
            raise

    async def subscribe_control_responses(
        self,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """
        Subscribe to control response messages from the FastStream bridge and forward each message to the provided callback.
        
        Parameters:
            callback (Callable[[Dict[str, Any]], Awaitable[None]]): Async function invoked for every received message. It will be called with a dictionary containing:
                - stream: `"CONTROL_RESPONSES"`
                - timestamp: ISO 8601 timestamp string when the message was processed
                - subject: the NATS subject of the message (or `None` if unavailable)
                - data: the decoded JSON payload of the message
        
        Raises:
            RuntimeError: If the client is not connected to NATS.
        """
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
            except Exception as e:
                print(f"Error processing CONTROL_RESPONSES message: {e}")

        subject = os.getenv("RESPONSES_CONTROL_SUBJECT", RESPONSES_CONTROL)
        try:
            sub = await self.nc.subscribe(subject, cb=message_handler)
            self.subscriptions["CONTROL_RESPONSES"] = sub
            print(f"✅ Subscribed to CONTROL_RESPONSES: {subject}")
        except Exception as e:
            print(f"❌ Failed to subscribe to CONTROL_RESPONSES: {e}")
            raise

    async def subscribe_qiki_proposals(
        self,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """
        Subscribe to QIKI proposal batches from core NATS and forward each message to the provided callback.
        
        The callback is invoked with a dictionary containing the keys:
        - `stream`: the string "QIKI_PROPOSALS"
        - `timestamp`: ISO 8601 timestamp when the message was processed
        - `subject`: the NATS subject on which the message was received (or None)
        - `data`: the decoded JSON payload
        
        Parameters:
            callback (Callable[[Dict[str, Any]], Awaitable[None]]): Async function called for each incoming message with the described dictionary payload.
        
        Raises:
            RuntimeError: If the NATS client is not connected.
        """
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        async def message_handler(msg):
            """
            Handle an incoming NATS message for QIKI proposals by decoding JSON and invoking the subscription callback with a structured payload.
            
            Parameters:
                msg: NATS message object whose `data` is a JSON-encoded bytes payload and which may have a `subject` attribute.
            
            Notes:
                On processing failure, an error message is printed.
            """
            try:
                data = json.loads(msg.data.decode())
                await callback(
                    {
                        "stream": "QIKI_PROPOSALS",
                        "timestamp": datetime.now().isoformat(),
                        "subject": getattr(msg, "subject", None),
                        "data": data,
                    }
                )
            except Exception as e:
                print(f"Error processing QIKI_PROPOSALS message: {e}")

        subject = os.getenv("QIKI_PROPOSALS_SUBJECT", QIKI_PROPOSALS_V1)
        try:
            sub = await self.nc.subscribe(subject, cb=message_handler)
            self.subscriptions["QIKI_PROPOSALS"] = sub
            print(f"✅ Subscribed to QIKI_PROPOSALS: {subject}")
        except Exception as e:
            print(f"❌ Failed to subscribe to QIKI_PROPOSALS: {e}")
            raise
            
    async def get_jetstream_info(self) -> Dict[str, Any]:
        """
        Retrieve high-level JetStream account statistics.
        
        Returns a dictionary with keys "memory", "storage", "streams", and "consumers" containing the corresponding account values. If an error occurs while fetching info, an empty dict is returned.
        
        Raises:
            RuntimeError: If the client is not connected to JetStream.
        """
        if not self.js:
            raise RuntimeError("Not connected to JetStream")
            
        try:
            info = await self.js.account_info()
            return {
                "memory": info.memory,
                "storage": info.storage,
                "streams": info.streams,
                "consumers": info.consumers
            }
        except Exception as e:
            print(f"Error getting JetStream info: {e}")
            return {}


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