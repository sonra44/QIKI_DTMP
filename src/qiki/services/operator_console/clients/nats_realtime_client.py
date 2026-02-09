"""
Real-time NATS Client for Operator Console.

Handles actual QIKI data streams from JetStream.
"""

import asyncio
import json
import os
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

import nats
from nats.js import JetStreamContext
from nats.errors import TimeoutError, NoServersError

from qiki.shared.nats_subjects import EVENTS_V1_WILDCARD, RADAR_FRAMES, SYSTEM_TELEMETRY


@dataclass
class RadarFrame:
    """Radar frame data structure."""

    frame_id: str
    sensor_id: str
    timestamp: datetime
    detections: List[Dict[str, Any]]


@dataclass
class RadarTrack:
    """Radar track data structure."""

    track_id: str
    position: tuple  # (x, y)
    velocity: float
    heading: float
    classification: str
    confidence: float


class RealtimeNATSClient:
    """Real-time NATS client for QIKI telemetry."""

    def __init__(self, url: Optional[str] = None):
        """Initialize NATS client."""
        env_url = os.getenv("NATS_URL", "nats://localhost:4222") or "nats://localhost:4222"
        self.url: str = url if url is not None else env_url
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[JetStreamContext] = None
        self.subscriptions: Dict[str, Any] = {}
        self.callbacks: Dict[str, List[Callable[..., Any]]] = {}
        self.latest_data: Dict[str, Any] = {"radar_frames": [], "tracks": [], "telemetry": {}, "events": []}

    async def connect(self) -> None:
        """Connect to NATS server and initialize JetStream."""
        try:
            self.nc = await nats.connect(
                servers=[self.url],
                connect_timeout=5,
                reconnect_time_wait=1,
                max_reconnect_attempts=-1,  # Infinite reconnect
            )
            self.js = self.nc.jetstream()
            print(f"✅ Connected to NATS at {self.url}")

            # Get JetStream info
            info = await self.js.account_info()
            print(f"📊 JetStream - Streams: {info.streams}, Storage: {info.storage} bytes")

        except (NoServersError, TimeoutError) as e:
            print(f"❌ Failed to connect to NATS: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self.nc:
            # Unsubscribe from all subscriptions
            for sub in self.subscriptions.values():
                await sub.unsubscribe()

            await self.nc.drain()
            await self.nc.close()
            print("Disconnected from NATS")

    def register_callback(self, stream: str, callback: Callable) -> None:
        """Register a callback for a specific stream."""
        if stream not in self.callbacks:
            self.callbacks[stream] = []
        self.callbacks[stream].append(callback)

    async def subscribe_all(self) -> None:
        """Subscribe to all QIKI streams."""
        await self.subscribe_radar_frames()
        await self.subscribe_system_telemetry()
        await self.subscribe_events()

    async def subscribe_radar_frames(self) -> None:
        """Subscribe to radar frame streams."""
        if not self.js:
            raise RuntimeError("Not connected to JetStream")
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        async def message_handler(msg):
            """Handle incoming radar frame messages."""
            try:
                # Parse the message
                data = json.loads(msg.data.decode())

                # Create RadarFrame object
                frame = RadarFrame(
                    frame_id=data.get("frame_id", "unknown"),
                    sensor_id=data.get("sensor_id", "unknown"),
                    timestamp=datetime.now(),
                    detections=data.get("detections", []),
                )

                # Store latest data
                self.latest_data["radar_frames"].append(
                    {
                        "timestamp": frame.timestamp.isoformat(),
                        "frame_id": frame.frame_id,
                        "detections": len(frame.detections),
                    }
                )

                # Keep only last 100 frames
                if len(self.latest_data["radar_frames"]) > 100:
                    self.latest_data["radar_frames"] = self.latest_data["radar_frames"][-100:]

                # Call registered callbacks
                for callback in self.callbacks.get("radar_frames", []):
                    await callback(frame)

                ack = getattr(msg, "ack", None)
                if callable(ack):
                    await ack()

            except Exception as e:
                print(f"Error processing radar frame: {e}")

        # Subscribe to the radar frames subject
        try:
            # Try to subscribe to the actual QIKI radar stream
            sub = await self.nc.subscribe(RADAR_FRAMES, cb=message_handler)
            self.subscriptions["radar_frames"] = sub
            print(f"✅ Subscribed to radar frames ({RADAR_FRAMES})")

        except Exception as e:
            print(f"⚠️ Could not subscribe to JetStream, falling back to regular NATS: {e}")
            # Fallback to legacy subject (deprecated)
            try:
                legacy_subject = "qiki.radar.v1.frames"
                sub = await self.nc.subscribe(legacy_subject, cb=message_handler)
                self.subscriptions["radar_frames"] = sub
                print(f"✅ Subscribed to radar frames ({legacy_subject}) [fallback]")
            except Exception as e2:
                print(f"❌ Failed to subscribe to radar frames: {e2}")

    async def subscribe_system_telemetry(self) -> None:
        """Subscribe to system telemetry stream."""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        async def message_handler(msg):
            """Handle telemetry messages."""
            try:
                data = json.loads(msg.data.decode())
                power = data.get("power", {}) if isinstance(data.get("power"), dict) else {}
                soc_pct = power.get("soc_pct")
                if soc_pct is None:
                    # Legacy compatibility: older publishers may still send top-level battery.
                    soc_pct = data.get("battery", 100)

                # Update telemetry data
                self.latest_data["telemetry"].update(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "position_x": data.get("position", {}).get("x", 0),
                        "position_y": data.get("position", {}).get("y", 0),
                        "position_z": data.get("position", {}).get("z", 0),
                        "velocity": data.get("velocity", 0),
                        "heading": data.get("heading", 0),
                        "soc_pct": soc_pct,
                        "battery": soc_pct,  # legacy alias for older console variants
                        # no-mocks: keep missing values as None, don't invent 0%
                        "cpu_usage": data.get("cpu_usage"),
                        "memory_usage": data.get("memory_usage"),
                    }
                )

                # Call callbacks
                for callback in self.callbacks.get("telemetry", []):
                    await callback(self.latest_data["telemetry"])

            except Exception as e:
                print(f"Error processing telemetry: {e}")

        # Subscribe to telemetry
        try:
            sub = await self.nc.subscribe(SYSTEM_TELEMETRY, cb=message_handler)
            self.subscriptions["telemetry"] = sub
            print("✅ Subscribed to system telemetry")
        except Exception as e:
            print(f"⚠️ Could not subscribe to telemetry: {e}")

    async def subscribe_events(self) -> None:
        """Subscribe to system events (Guard Rules, FSM transitions, etc)."""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        async def message_handler(msg):
            """Handle event messages."""
            try:
                data = json.loads(msg.data.decode())

                event = {
                    "timestamp": datetime.now().isoformat(),
                    "type": data.get("type", "unknown"),
                    "severity": data.get("severity", "info"),
                    "message": data.get("message", ""),
                    "details": data.get("details", {}),
                }

                # Store event
                self.latest_data["events"].append(event)

                # Keep only last 50 events
                if len(self.latest_data["events"]) > 50:
                    self.latest_data["events"] = self.latest_data["events"][-50:]

                # Call callbacks
                for callback in self.callbacks.get("events", []):
                    await callback(event)

            except Exception as e:
                print(f"Error processing event: {e}")

        # Subscribe to events
        try:
            subject = os.getenv("EVENTS_SUBJECT", EVENTS_V1_WILDCARD)
            sub = await self.nc.subscribe(subject, cb=message_handler)
            self.subscriptions["events"] = sub
            print(f"✅ Subscribed to system events: {subject}")
        except Exception as e:
            print(f"⚠️ Could not subscribe to events: {e}")

    async def publish_command(self, command_type: str, payload: Dict[str, Any]) -> None:
        """Publish a command to the system."""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        subject = f"qiki.commands.{command_type}"

        try:
            message = json.dumps(
                {
                    "timestamp": datetime.now().isoformat(),
                    "command": command_type,
                    "payload": payload,
                    "source": "operator_console",
                }
            ).encode()

            await self.nc.publish(subject, message)
            print(f"📤 Published command '{command_type}' to {subject}")

        except Exception as e:
            print(f"❌ Failed to publish command: {e}")
            raise

    def get_latest_data(self) -> Dict[str, Any]:
        """Get the latest cached data."""
        return self.latest_data

    async def get_stream_info(self) -> Dict[str, Any]:
        """Get information about JetStream streams."""
        if not self.js:
            return {"error": "Not connected to JetStream"}

        try:
            info = await self.js.account_info()

            # Try to get stream list
            streams: List[Any] = []
            # This is a simplified version - actual implementation would enumerate streams

            return {
                "account": {
                    "memory": info.memory,
                    "storage": info.storage,
                    "streams": info.streams,
                    "consumers": info.consumers,
                },
                "streams": streams,
            }
        except Exception as e:
            return {"error": str(e)}


# Test function
async def test_realtime_client():
    """Test the real-time NATS client."""
    client = RealtimeNATSClient()

    # Define test callbacks
    async def on_radar_frame(frame: RadarFrame):
        print(f"📡 Radar Frame: {frame.frame_id}, Detections: {len(frame.detections)}")

    async def on_telemetry(data: dict):
        print(f"📊 Telemetry: Position({data.get('position_x')}, {data.get('position_y')})")

    async def on_event(event: dict):
        print(f"⚡ Event: {event['type']} - {event['message']}")

    try:
        # Connect
        await client.connect()

        # Register callbacks
        client.register_callback("radar_frames", on_radar_frame)
        client.register_callback("telemetry", on_telemetry)
        client.register_callback("events", on_event)

        # Subscribe to all streams
        await client.subscribe_all()

        # Get stream info
        info = await client.get_stream_info()
        print(f"Stream Info: {info}")

        # Test publishing a command
        await client.publish_command("simulation.start", {"speed": 1.0})

        # Run for a while
        print("\n🎯 Listening for messages... (Press Ctrl+C to stop)")
        await asyncio.sleep(30)

        # Get latest data
        latest = client.get_latest_data()
        print("\n📈 Latest data summary:")
        print(f"  - Radar frames: {len(latest['radar_frames'])}")
        print(f"  - Events: {len(latest['events'])}")
        print(f"  - Telemetry: {latest['telemetry']}")

    except KeyboardInterrupt:
        print("\n⏹️ Stopping...")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_realtime_client())
