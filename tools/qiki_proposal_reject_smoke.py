import asyncio
import json
import os
import time
import sys
from typing import Any
from uuid import uuid4

from qiki.shared.models.qiki_chat import QikiChatRequestV1, QikiChatResponseV1
from qiki.shared.nats_subjects import QIKI_INTENTS, QIKI_RESPONSES


async def _request_once(
    nc,
    *,
    text: str,
    selection_kind: str,
    selection_id: str | None,
    decision: dict[str, str] | None = None,
) -> QikiChatResponseV1:
    req = QikiChatRequestV1(
        request_id=uuid4(),
        ts_epoch_ms=int(time.time() * 1000),
        input={"text": text, "lang_hint": "auto"},
        decision=decision,
        ui_context={"screen": "QIKI/QIKI", "selection": {"kind": selection_kind, "id": selection_id}},
    )

    got: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()

    async def handler(msg) -> None:
        if got.done():
            return
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if isinstance(payload, dict) and str(payload.get("request_id") or payload.get("requestId")) == str(
            req.request_id
        ):
            got.set_result(payload)

    sub = await nc.subscribe(QIKI_RESPONSES, cb=handler)
    try:
        await nc.publish(QIKI_INTENTS, req.model_dump_json().encode("utf-8"))
        timeout_s = float(os.getenv("QIKI_PROPOSAL_REJECT_SMOKE_TIMEOUT_SEC", "5.0"))
        payload = await asyncio.wait_for(got, timeout=timeout_s)
        return QikiChatResponseV1.model_validate(payload)
    finally:
        try:
            await sub.unsubscribe()
        except Exception:
            print("WARN: qiki_proposal_reject_smoke unsubscribe failed", file=sys.stderr)


async def main() -> int:
    try:
        import nats
    except Exception as exc:  # pragma: no cover
        print(f"nats import failed: {exc}")
        return 2

    nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
    timeout_s = float(os.getenv("QIKI_PROPOSAL_REJECT_SMOKE_TIMEOUT_SEC", "5.0"))

    nc = await nats.connect(
        servers=[nats_url],
        connect_timeout=min(3.0, timeout_s),
        allow_reconnect=False,
        max_reconnect_attempts=0,
    )
    try:
        resp = await _request_once(
            nc,
            text=os.getenv("QIKI_INTENT_TEXT", "dock.on"),
            selection_kind="none",
            selection_id=None,
        )
        if not resp.proposals:
            print("BAD: no proposals returned")
            return 1

        pid = str(resp.proposals[0].proposal_id)
        reject = await _request_once(
            nc,
            text=f"proposal reject {pid}",
            selection_kind="proposal",
            selection_id=pid,
            decision={"proposal_id": pid, "decision": "REJECT"},
        )
        title = reject.reply.title.en if reject.reply else ""
        if title.lower() != "rejected":
            print(f"BAD: expected Rejected, got {title!r}")
            return 1
        print(f"OK: rejected proposal_id={pid}")
        return 0
    except TimeoutError:
        print(f"TIMEOUT: no qiki response on {QIKI_RESPONSES} within {timeout_s}s")
        return 1
    finally:
        await nc.drain()
        await nc.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
