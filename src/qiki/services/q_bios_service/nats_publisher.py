from __future__ import annotations

import asyncio
import json
from typing import Any

import nats


class NatsJsonPublisher:
    def __init__(self, *, nats_url: str) -> None:
        self._nats_url = nats_url
        self._nc: Any = None
        self._lock = asyncio.Lock()

    async def _connect(self) -> Any:
        return await nats.connect(
            servers=[self._nats_url],
            connect_timeout=5,
            reconnect_time_wait=1,
            max_reconnect_attempts=-1,
        )

    async def _close(self) -> None:
        if self._nc is None:
            return
        try:
            await self._nc.drain()
        except Exception:
            pass
        try:
            await self._nc.close()
        except Exception:
            pass
        self._nc = None

    async def publish_json(self, *, subject: str, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, default=str).encode("utf-8")
        last_exc: Exception | None = None

        for attempt in range(1, 4):
            async with self._lock:
                try:
                    if self._nc is None or not getattr(self._nc, "is_connected", False):
                        await self._close()
                        self._nc = await self._connect()
                    await self._nc.publish(subject, data)
                    return
                except Exception as exc:
                    last_exc = exc
                    await self._close()

            await asyncio.sleep(min(2.0, 0.2 * attempt))

        assert last_exc is not None
        raise last_exc

    async def close(self) -> None:
        async with self._lock:
            await self._close()


async def publish_json(*, nats_url: str, subject: str, payload: dict[str, Any]) -> None:
    publisher = NatsJsonPublisher(nats_url=nats_url)
    try:
        await publisher.publish_json(subject=subject, payload=payload)
    finally:
        await publisher.close()
