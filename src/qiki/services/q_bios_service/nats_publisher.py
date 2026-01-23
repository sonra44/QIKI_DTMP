from __future__ import annotations

import json
from typing import Any

import nats


async def publish_json(*, nats_url: str, subject: str, payload: dict[str, Any]) -> None:
    nc = await nats.connect(servers=[nats_url], connect_timeout=2, reconnect_time_wait=1, max_reconnect_attempts=1)
    try:
        data = json.dumps(payload, default=str).encode("utf-8")
        await nc.publish(subject, data)
    finally:
        try:
            await nc.drain()
        except Exception:
            pass
        await nc.close()

