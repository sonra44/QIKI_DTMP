"""
NATS Client for Operator Console.

Handles connection to NATS JetStream and subscribes to telemetry streams.
"""

import asyncio
import json
import os
from typing import Any, Callable, Dict, Optional
from datetime import datetime

import nats
from nats.js import JetStreamContext
from nats.errors import TimeoutError, NoServersError


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
            self.nc = await nats.connect(self.url)
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
            
    async def subscribe_radar_sr(self, callback: Callable[[Dict], None]) -> None:
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
            sub = await self.js.subscribe(
                "RADAR.frames.sr",
                cb=message_handler,
                durable="operator-console-sr",
                manual_ack=True
            )
            self.subscriptions["RADAR_SR"] = sub
            print("✅ Subscribed to RADAR_SR stream")
        except Exception as e:
            print(f"❌ Failed to subscribe to RADAR_SR: {e}")
            raise
            
    async def subscribe_radar_lr(self, callback: Callable[[Dict], None]) -> None:
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
            sub = await self.js.subscribe(
                "RADAR.frames.lr",
                cb=message_handler,
                durable="operator-console-lr",
                manual_ack=True
            )
            self.subscriptions["RADAR_LR"] = sub
            print("✅ Subscribed to RADAR_LR stream")
        except Exception as e:
            print(f"❌ Failed to subscribe to RADAR_LR: {e}")
            raise
            
    async def subscribe_tracks(self, callback: Callable[[Dict], None]) -> None:
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
            sub = await self.js.subscribe(
                "RADAR.tracks",
                cb=message_handler,
                durable="operator-console-tracks",
                manual_ack=True
            )
            self.subscriptions["TRACKS"] = sub
            print("✅ Subscribed to TRACKS stream")
        except Exception as e:
            print(f"❌ Failed to subscribe to TRACKS: {e}")
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
            payload = json.dumps(command).encode()
            await self.nc.publish(subject, payload)
            print(f"📤 Published command to {subject}: {command}")
        except Exception as e:
            print(f"❌ Failed to publish command: {e}")
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
