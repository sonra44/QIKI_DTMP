from __future__ import annotations

import asyncio
import json
import os
import time
import sys
from typing import Any
from uuid import uuid4

from qiki.shared.models.qiki_chat import QikiChatRequestV1, QikiChatResponseV1
from qiki.shared.nats_subjects import QIKI_INTENTS, QIKI_RESPONSES


async def main() -> int:
    try:
        import nats
    except Exception as exc:  # pragma: no cover
        print(f"nats import failed: {exc}")
        return 2

    nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
    intents_subject = os.getenv("QIKI_INTENTS_SUBJECT", QIKI_INTENTS)
    responses_subject = os.getenv("QIKI_RESPONSES_SUBJECT", QIKI_RESPONSES)
    timeout_s = float(os.getenv("QIKI_INTENT_SMOKE_TIMEOUT_SEC", "5.0"))
    text = os.getenv("QIKI_INTENT_TEXT", "ping")

    req = QikiChatRequestV1(
        request_id=uuid4(),
        ts_epoch_ms=int(time.time() * 1000),
        input={"text": text, "lang_hint": "auto"},
    )

    # Avoid hanging indefinitely on misconfigured network; fail fast.
    nc = await nats.connect(
        servers=[nats_url],
        connect_timeout=3,
        allow_reconnect=False,
        max_reconnect_attempts=0,
    )
    got: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()

    async def handler(msg) -> None:
        if got.done():
            return
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if isinstance(payload, dict) and str(payload.get("request_id") or payload.get("requestId")) == str(req.request_id):
            got.set_result(payload)

    sub = await nc.subscribe(responses_subject, cb=handler)
    try:
        await nc.publish(intents_subject, req.model_dump_json().encode("utf-8"))
        payload = await asyncio.wait_for(got, timeout=timeout_s)
        resp = QikiChatResponseV1.model_validate(payload)
        if resp.request_id != req.request_id:
            print(f"BAD: request_id mismatch: expected={req.request_id} got={resp.request_id}")
            return 1
        print(f"OK: received qiki response for request_id={resp.request_id} ok={resp.ok} mode={resp.mode.value}")
        return 0
    except TimeoutError:
        print(f"TIMEOUT: no qiki response on {responses_subject} within {timeout_s}s")
        return 1
    finally:
        try:
            await sub.unsubscribe()
        except Exception:
            print("WARN: qiki_intent_smoke unsubscribe failed", file=sys.stderr)
        await nc.drain()
        await nc.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
