from __future__ import annotations

import asyncio
import json
import os
import signal
from typing import Optional

import nats
from nats.errors import TimeoutError, NoServersError

from qiki.services.qiki_chat.handler import (
    build_invalid_request_response,
    handle_chat_request,
)
from qiki.shared.models.qiki_chat import QikiChatRequestV1


CHAT_SUBJECT = "qiki.chat.v1"


async def _serve(nats_url: str) -> None:
    nc: Optional[nats.NATS] = None
    try:
        nc = await nats.connect(
            servers=[nats_url],
            connect_timeout=5,
            reconnect_time_wait=1,
            max_reconnect_attempts=-1,
        )
    except (NoServersError, TimeoutError) as exc:
        raise RuntimeError(f"Failed to connect to NATS at {nats_url}: {exc}") from exc

    async def on_msg(msg) -> None:
        try:
            payload = json.loads(msg.data.decode("utf-8"))
            request = QikiChatRequestV1.model_validate(payload)
            response = handle_chat_request(request)
            await msg.respond(response.model_dump_json(ensure_ascii=False).encode("utf-8"))
        except Exception:
            await msg.respond(build_invalid_request_response(raw_request_id=None))

    await nc.subscribe(CHAT_SUBJECT, cb=on_msg)

    stop_event = asyncio.Event()

    def _stop(*_args) -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:  # pragma: no cover
            signal.signal(sig, lambda *_: _stop())

    await stop_event.wait()
    await nc.drain()
    await nc.close()


def main() -> None:
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222") or "nats://localhost:4222"
    asyncio.run(_serve(nats_url))


if __name__ == "__main__":
    main()

