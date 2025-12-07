#!/usr/bin/env python3
"""Test NATS connection."""

import asyncio
from clients.nats_client import NATSClient


async def test_connection():
    """Test NATS connection and JetStream."""
    client = NATSClient()
    
    try:
        # Connect to NATS
        await client.connect()
        print("✅ Successfully connected to NATS!")
        
        # Get JetStream info
        info = await client.get_jetstream_info()
        print("\n📊 JetStream Info:")
        print(f"  - Memory: {info.get('memory', 'N/A')}")
        print(f"  - Storage: {info.get('storage', 'N/A')}")
        print(f"  - Streams: {info.get('streams', 'N/A')}")
        print(f"  - Consumers: {info.get('consumers', 'N/A')}")
        
        print("\n✅ NATS connection test passed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_connection())
