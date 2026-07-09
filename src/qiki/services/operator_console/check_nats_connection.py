#!/usr/bin/env python3
"""Ручной скрипт проверки NATS-соединения (НЕ pytest-тест).

Санация 0050: раньше жил как test_nats_connection.py — pytest собирал его,
top-level импорт несуществующего пакета `clients` валил коллекцию всего
src-дерева. Переименован + импорт починен на канонный путь клиента.
"""

import asyncio

from qiki.services.operator_console.clients.nats_client import NATSClient


async def check_connection():
    """Проверить NATS-соединение и JetStream."""
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
    asyncio.run(check_connection())
