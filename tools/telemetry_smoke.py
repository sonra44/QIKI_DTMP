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
    subject = os.getenv("SYSTEM_TELEMETRY_SUBJECT", "qiki.telemetry")
    timeout_s = float(os.getenv("TELEMETRY_SMOKE_TIMEOUT_SEC", "3.0"))

    nc = await nats.connect(servers=[nats_url], connect_timeout=2)
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
        pos = payload.get("position") if isinstance(payload, dict) else None
        if not isinstance(pos, dict) or not {"x", "y", "z"} <= set(pos.keys()):
            print(f"BAD: telemetry missing 3D position on {subject}: {payload}")
            return 1
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            print(f"BAD: telemetry schema_version != 1 on {subject}: {payload}")
            return 1
        if "ts_unix_ms" not in payload:
            print(f"BAD: telemetry missing ts_unix_ms on {subject}: {payload}")
            return 1
        power = payload.get("power") if isinstance(payload, dict) else None
        if not isinstance(power, dict) or not {
            "soc_pct",
            "power_in_w",
            "power_out_w",
            "bus_v",
            "bus_a",
        } <= set(power.keys()):
            print(f"BAD: telemetry missing power/EPS fields on {subject}: {payload}")
            return 1
        attitude = payload.get("attitude") if isinstance(payload, dict) else None
        if not isinstance(attitude, dict) or not {
            "roll_rad",
            "pitch_rad",
            "yaw_rad",
        } <= set(attitude.keys()):
            print(f"BAD: telemetry missing attitude fields on {subject}: {payload}")
            return 1
        thermal = payload.get("thermal") if isinstance(payload, dict) else None
        if not isinstance(thermal, dict):
            print(f"BAD: telemetry missing thermal block on {subject}: {payload}")
            return 1
        nodes = thermal.get("nodes") if isinstance(thermal, dict) else None
        if not isinstance(nodes, list) or not nodes:
            print(f"BAD: telemetry missing thermal nodes on {subject}: {payload}")
            return 1
        print(f"OK: received telemetry on {subject}: {payload}")
        return 0
    except TimeoutError:
        print(f"TIMEOUT: no telemetry on {subject} within {timeout_s}s")
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
