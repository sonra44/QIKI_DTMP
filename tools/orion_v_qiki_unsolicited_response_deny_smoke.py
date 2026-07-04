"""M0c live-proof: непрошеный publish в qiki.responses.qiki отклоняется живой консолью.

Smoke повторяет канал атаки №8в (publish чужого ответа прямо в шину) и
доказывает, что ORION V:
1) отклоняет ответ с request_id, которого нет в её _qiki_pending (deny),
2) принимает ответ на request_id, который она ждёт (positive control).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from uuid import UUID

import nats

from qiki.services.operator_console.orion_v.app import OrionVApp

RESPONSES_SUBJECT = os.getenv("QIKI_RESPONSES_SUBJECT", "qiki.responses.qiki")


def _response_payload(request_id: str, marker: str) -> dict[str, object]:
    return {
        "version": 1,
        "request_id": request_id,
        "ok": True,
        "mode": "FACTORY",
        "reply": {
            "title": {"en": marker, "ru": marker},
            "body": {"en": f"{marker} body", "ru": f"{marker} тело"},
        },
        "legality": None,
        "trust_signals": [],
        "consequence": None,
        "proposals": [],
        "warnings": [],
        "error": None,
    }


async def _wait_until(predicate, *, timeout_s: float, step_s: float, label: str) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(step_s)
    raise AssertionError(f"timeout while waiting for {label}")


async def _main() -> None:
    app = OrionVApp()
    async with app.run_test(size=(160, 48)) as pilot:
        await _wait_until(
            lambda: app._nats_client.connection_state == "connected",
            timeout_s=10.0,
            step_s=0.1,
            label="NATS connection",
        )
        nats_url = os.getenv("NATS_URL", "nats://nats:4222")
        nc = await nats.connect(servers=[nats_url], connect_timeout=3)
        try:
            # 1) АТАКА: request_id консоль не выдавала -> ответ должен быть отклонён.
            spoofed_id = str(UUID(int=666))
            await nc.publish(
                RESPONSES_SUBJECT,
                json.dumps(_response_payload(spoofed_id, "SPOOFED")).encode("utf-8"),
            )
            await nc.flush()
            await asyncio.sleep(1.0)
            await pilot.pause()
            assert app._qiki_last_response is None, "spoofed response was ACCEPTED (deny gate failed)"
            assert len(app._qiki_voice_ledger) == 0, "spoofed response reached qiki_voice ledger"
            print("[smoke] deny OK: непрошеный ответ не принят (ledger пуст, last_response=None)")

            # 2) POSITIVE CONTROL: request_id зарегистрирован как pending -> ответ принимается.
            expected_id = str(UUID(int=777))
            app._qiki_pending[expected_id] = (time.time(), "smoke positive control")
            await nc.publish(
                RESPONSES_SUBJECT,
                json.dumps(_response_payload(expected_id, "EXPECTED")).encode("utf-8"),
            )
            await nc.flush()
            await _wait_until(
                lambda: app._qiki_last_response is not None,
                timeout_s=5.0,
                step_s=0.1,
                label="expected response acceptance",
            )
            assert str(app._qiki_last_response.request_id) == expected_id
            assert len(app._qiki_voice_ledger) == 1
            assert expected_id not in app._qiki_pending
            print("[smoke] accept OK: ожидаемый ответ принят, pending снят, реплика в ленте")
        finally:
            await nc.close()

    print("[smoke] M0c PASS: deny непрошеных + accept ожидаемых на живой шине")


if __name__ == "__main__":
    asyncio.run(_main())
