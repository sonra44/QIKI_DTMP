from __future__ import annotations

import asyncio
import json
import os
from typing import Any


async def main() -> int:
    try:
        import nats
    except Exception as exc:  # pragma: no cover
        print(f"nats import failed: {exc}")
        return 2

    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    subject = os.getenv("BIOS_STATUS_SUBJECT", "qiki.events.v1.bios_status")
    timeout_s = float(os.getenv("BIOS_STATUS_SMOKE_TIMEOUT_SEC", "5.0"))

    nc = await nats.connect(servers=[nats_url], connect_timeout=5)
    got: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()

    async def handler(msg) -> None:
        if got.done():
            return
        try:
            got.set_result(json.loads(msg.data.decode("utf-8")))
        except Exception:
            got.set_result({"raw": msg.data.decode("utf-8", errors="replace")})

    sub = await nc.subscribe(subject, cb=handler)
    try:
        payload = await asyncio.wait_for(got, timeout=timeout_s)
        if not isinstance(payload, dict):
            print(f"BAD: bios status payload is not a dict on {subject}: {payload}")
            return 1
        if not isinstance(payload.get("post_results"), list):
            print(f"BAD: bios status missing post_results list on {subject}: {payload}")
            return 1
        if payload.get("event_schema_version") != 1:
            print(f"BAD: bios status event_schema_version != 1 on {subject}: {payload}")
            return 1
        if "bios_version" not in payload:
            print(f"BAD: bios status missing bios_version on {subject}: {payload}")
            return 1
        print(f"OK: received bios status on {subject}: {payload}")
        return 0
    except TimeoutError:
        print(f"TIMEOUT: no bios status on {subject} within {timeout_s}s")
        return 1
    finally:
        try:
            await sub.unsubscribe()
        except Exception:
            pass
        await nc.drain()
        await nc.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
