from __future__ import annotations

import argparse
import asyncio
import os
import time
from uuid import uuid4

import nats

from qiki.shared.models.qiki_chat import QikiChatInput, QikiChatRequestV1, QikiMode


CHAT_SUBJECT = "qiki.chat.v1"


async def _ask(nats_url: str, text: str, timeout_sec: float) -> int:
    nc = await nats.connect(servers=[nats_url], connect_timeout=5)
    try:
        request = QikiChatRequestV1(
            request_id=uuid4(),
            ts_epoch_ms=int(time.time() * 1000),
            mode_hint=QikiMode.FACTORY,
            input=QikiChatInput(text=text, lang_hint="auto"),
        )
        msg = await nc.request(
            CHAT_SUBJECT,
            request.model_dump_json(ensure_ascii=False).encode("utf-8"),
            timeout=timeout_sec,
        )
        print(msg.data.decode("utf-8"))
        return 0
    finally:
        await nc.drain()
        await nc.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask QIKI over NATS request/reply.")
    parser.add_argument("text", help="Free-text question/intent for QIKI")
    parser.add_argument(
        "--nats-url",
        default=os.getenv("NATS_URL", "nats://localhost:4222") or "nats://localhost:4222",
        help="NATS URL (default from NATS_URL env)",
    )
    parser.add_argument("--timeout", type=float, default=3.0, help="Request timeout (sec)")
    args = parser.parse_args()

    raise SystemExit(asyncio.run(_ask(args.nats_url, args.text, args.timeout)))


if __name__ == "__main__":
    main()

