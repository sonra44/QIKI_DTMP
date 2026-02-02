from __future__ import annotations

import asyncio
from argparse import ArgumentParser
import json
import os
import time
from typing import Any
from uuid import uuid4

from qiki.shared.models.qiki_chat import QikiChatRequestV1, QikiChatResponseV1, QikiMode
from qiki.shared.nats_subjects import (
    EVENTS_STREAM_NAME,
    QIKI_INTENTS,
    QIKI_RESPONSES,
    SYSTEM_MODE_EVENT,
)


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="QIKI system_mode smoke (realtime + JetStream persisted)")
    parser.add_argument(
        "--persisted-only",
        action="store_true",
        help="Only verify the last persisted system_mode event in JetStream (no publishing).",
    )
    parser.add_argument(
        "--expect-mode",
        choices=[m.value for m in QikiMode],
        default=None,
        help="Optional expected mode for persisted-only checks (FACTORY|MISSION).",
    )
    return parser


async def main() -> int:
    args = _build_parser().parse_args()
    try:
        import nats
    except Exception as exc:  # pragma: no cover
        print(f"nats import failed: {exc}")
        return 2

    nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
    timeout_s = float(os.getenv("SYSTEM_MODE_SMOKE_TIMEOUT_SEC", "5.0"))

    nc = await nats.connect(servers=[nats_url], connect_timeout=3, allow_reconnect=False)
    js = nc.jetstream()

    async def get_persisted(
        *, deadline_epoch: float, expect_mode: QikiMode | None
    ) -> dict[str, Any] | None:
        last_exc: Exception | None = None
        while time.time() < deadline_epoch:
            try:
                msg = await js.get_last_msg(EVENTS_STREAM_NAME, SYSTEM_MODE_EVENT)
            except Exception as exc:
                last_exc = exc
                await asyncio.sleep(0.2)
                continue
            try:
                payload = json.loads(msg.data.decode("utf-8"))
            except Exception as exc:
                last_exc = exc
                await asyncio.sleep(0.2)
                continue
            if not isinstance(payload, dict):
                last_exc = ValueError("system_mode payload is not a dict")
                await asyncio.sleep(0.2)
                continue
            mode_raw = payload.get("mode")
            if expect_mode is not None and mode_raw != expect_mode.value:
                await asyncio.sleep(0.2)
                continue
            return payload

        if last_exc is not None:
            print(f"BAD: no persisted system_mode event in JetStream: {last_exc}")
        else:
            print("BAD: no persisted system_mode event in JetStream (timeout)")
        return None

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
            except Exception as exc:
                print(f"WARN: failed to unsubscribe from {QIKI_RESPONSES}: {exc}")
            try:
                await event_sub.unsubscribe()
            except Exception as exc:
                print(f"WARN: failed to unsubscribe from {SYSTEM_MODE_EVENT}: {exc}")

    try:
        if args.persisted_only:
            expect_mode = QikiMode(args.expect_mode) if args.expect_mode else None
            payload = await get_persisted(deadline_epoch=time.time() + timeout_s, expect_mode=expect_mode)
            if payload is None:
                return 1
            mode_raw = payload.get("mode")
            ts_epoch = payload.get("ts_epoch")
            print(f"OK: persisted system_mode in JetStream: mode={mode_raw} ts_epoch={ts_epoch}")
            return 0

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

        persisted_mission = await get_persisted(
            deadline_epoch=time.time() + timeout_s, expect_mode=QikiMode.MISSION
        )
        if persisted_mission is None:
            return 1

        # Restore baseline for operators.
        await set_mode(QikiMode.FACTORY)
        persisted_factory = await get_persisted(
            deadline_epoch=time.time() + timeout_s, expect_mode=QikiMode.FACTORY
        )
        if persisted_factory is None:
            return 1

        print("OK: system mode set + event published + persisted")
        return 0
    finally:
        await nc.drain()
        await nc.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
