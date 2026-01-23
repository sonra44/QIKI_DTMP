from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any
from uuid import uuid4

from qiki.shared.models.qiki_chat import QikiChatRequestV1, QikiChatResponseV1, QikiMode
from qiki.shared.nats_subjects import (
    QIKI_INTENTS,
    QIKI_RESPONSES,
    SYSTEM_MODE_EVENT,
)


async def main() -> int:
    try:
        import nats
    except Exception as exc:  # pragma: no cover
        print(f"nats import failed: {exc}")
        return 2

    nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
    timeout_s = float(os.getenv("SYSTEM_MODE_SMOKE_TIMEOUT_SEC", "5.0"))

    nc = await nats.connect(servers=[nats_url], connect_timeout=3, allow_reconnect=False)

    async def set_mode(mode: QikiMode) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        got_resp: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        got_event: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()

        req = QikiChatRequestV1(
            request_id=uuid4(),
            ts_epoch_ms=int(time.time() * 1000),
            input={"text": f"mode {mode.value.lower()}", "lang_hint": "auto"},
        )

        async def resp_handler(msg) -> None:
            if got_resp.done():
                return
            try:
                payload = json.loads(msg.data.decode("utf-8"))
            except Exception:
                return
            if not isinstance(payload, dict):
                return
            rid = payload.get("request_id") or payload.get("requestId")
            if str(rid) != str(req.request_id):
                return
            got_resp.set_result(payload)

        async def event_handler(msg) -> None:
            if got_event.done():
                return
            try:
                payload = json.loads(msg.data.decode("utf-8"))
            except Exception:
                return
            if not isinstance(payload, dict):
                return
            if payload.get("mode") != mode.value:
                return
            got_event.set_result(payload)

        resp_sub = await nc.subscribe(QIKI_RESPONSES, cb=resp_handler)
        event_sub = await nc.subscribe(SYSTEM_MODE_EVENT, cb=event_handler)
        await nc.flush(timeout=2)

        try:
            await nc.publish(QIKI_INTENTS, req.model_dump_json().encode("utf-8"))
            await nc.flush(timeout=2)
            resp_raw = await asyncio.wait_for(got_resp, timeout=timeout_s)
            event_raw = await asyncio.wait_for(got_event, timeout=timeout_s)
            return resp_raw, event_raw
        finally:
            try:
                await resp_sub.unsubscribe()
            except Exception:
                pass
            try:
                await event_sub.unsubscribe()
            except Exception:
                pass

    try:
        resp_raw, event_raw = await set_mode(QikiMode.MISSION)
        resp = QikiChatResponseV1.model_validate(resp_raw) if isinstance(resp_raw, dict) else None
        if not resp or not resp.ok:
            print(f"BAD: qiki response is not ok: {resp_raw}")
            return 1
        if resp.mode != QikiMode.MISSION:
            print(f"BAD: response mode mismatch: {resp_raw}")
            return 1
        if not isinstance(event_raw, dict) or event_raw.get("mode") != QikiMode.MISSION.value:
            print(f"BAD: system_mode event mismatch: {event_raw}")
            return 1

        # Restore baseline for operators.
        await set_mode(QikiMode.FACTORY)

        print("OK: system mode set + event published")
        return 0
    finally:
        await nc.drain()
        await nc.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
