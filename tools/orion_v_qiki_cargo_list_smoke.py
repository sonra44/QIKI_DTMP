"""P1 live-proof (ADR-0019): «доложи отсек» по реальной шине → список из каталога.

Проверяет: живой policy-сервис отвечает докладом по грузовому отсеку, в ответе
есть все 5 записей каталога с остатками, proposals пуст (информация, не команда).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any
from uuid import uuid4

from qiki.shared.models.qiki_chat import QikiChatRequestV1
from qiki.shared.module_catalog import load_module_catalog
from qiki.shared.nats_connect import nats_auth_kwargs
from qiki.shared.nats_subjects import QIKI_INTENTS, QIKI_RESPONSES


async def main() -> None:
    import nats

    nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
    req = QikiChatRequestV1(
        request_id=uuid4(),
        ts_epoch_ms=int(time.time() * 1000),
        input={"text": "доложи отсек", "lang_hint": "ru"},
    )
    nc = await nats.connect(servers=[nats_url], connect_timeout=3, allow_reconnect=False, **nats_auth_kwargs())
    got: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()

    async def handler(msg) -> None:
        if got.done():
            return
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if isinstance(payload, dict) and str(payload.get("request_id")) == str(req.request_id):
            got.set_result(payload)

    sub = await nc.subscribe(QIKI_RESPONSES, cb=handler)
    try:
        await nc.publish(QIKI_INTENTS, req.model_dump_json().encode("utf-8"))
        payload = await asyncio.wait_for(got, timeout=8.0)
    finally:
        await sub.unsubscribe()
        await nc.close()

    body_ru = str(((payload.get("reply") or {}).get("body") or {}).get("ru") or "")
    assert payload.get("proposals") == [], "доклад по отсеку не должен нести proposals"

    catalog = load_module_catalog("/workspace/config/modules/catalog.json")
    assert catalog.ok, catalog.error_code
    for entry in catalog.entries:
        assert entry.module_id in body_ru, f"{entry.module_id} отсутствует в докладе"
        assert f"остаток {entry.quantity}" in body_ru or str(entry.quantity) in body_ru

    print("[smoke] доклад по отсеку получен по РЕАЛЬНОЙ шине от живого policy:")
    for line in body_ru.splitlines():
        print(f"  {line}")
    print(f"[smoke] P1 LIVE PASS: {len(catalog.entries)} записей каталога, proposals пуст")


if __name__ == "__main__":
    asyncio.run(main())
