from __future__ import annotations

import asyncio
import json
import os
import time
from types import SimpleNamespace

import nats
from textual.widgets import Static

import qiki.services.operator_console.orion_v.app as orion_v_app_module
from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.q_core_agent.qiki_orion_intents_service import _build_hostile_attack_block_response
from qiki.shared.models.qiki_chat import QikiChatRequestV1, QikiMode
from qiki.shared.nats_connect import nats_auth_kwargs

_INTENTS_SUBJECT = "qiki.intents.g2proof"
_RESPONSES_SUBJECT = "qiki.responses.qiki.g2proof"
_COMMAND_TEXT = "attack object UNBT9999"
_STATION_BLOCK_CODE = "STATION_COMBAT_PROTOCOL_BLOCK"
_HOSTILE_CONTEXT_OPEN_CODE = "HOSTILE_CONTEXT_OPEN_BY_FOE_TRACK"
_TERSE_REFUSAL_RU = "Нет. Протокол станции всё ещё блокирует бой здесь."


def _widget_text(widget: object) -> str:
    renderable = getattr(widget, "renderable", None)
    if hasattr(renderable, "plain"):
        return str(getattr(renderable, "plain"))
    if renderable is not None:
        return str(renderable)
    content = getattr(widget, "content", None)
    if hasattr(content, "plain"):
        return str(getattr(content, "plain"))
    if content is not None:
        return str(content)
    return str(widget)


async def _wait_until(predicate, *, timeout_s: float, step_s: float, label: str) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(step_s)
    raise AssertionError(f"timeout while waiting for {label}")


async def _hostile_intent_responder(stop_event: asyncio.Event) -> None:
    world_snapshots = [
        {
            "radar_tracks": [
                {"object_type": 3, "range_m": 12000.0, "quality": 0.96, "age_s": 0.2},
                {
                    "object_type": 2,
                    "range_m": 1800.0,
                    "quality": 0.91,
                    "age_s": 0.1,
                    "transponder_id": "UNBT9999",
                    "iff": 3,
                },
            ]
        },
        {
            "radar_tracks": [
                {
                    "object_type": 2,
                    "range_m": 4200.0,
                    "quality": 0.95,
                    "age_s": 0.1,
                    "transponder_id": "UNBT9999",
                    "iff": 2,
                }
            ]
        },
    ]
    agent = SimpleNamespace(context=SimpleNamespace(qiki_repeat_state={}))
    state = {"index": 0}
    nc = await nats.connect(
        servers=[os.getenv("NATS_URL", "nats://nats:4222")],
        connect_timeout=3,
        allow_reconnect=False,
        max_reconnect_attempts=0,
        **nats_auth_kwargs(),
    )

    async def handler(msg) -> None:
        payload = json.loads(msg.data.decode("utf-8"))
        req = QikiChatRequestV1.model_validate(payload)
        response = _build_hostile_attack_block_response(
            req=req,
            mode=QikiMode.FACTORY,
            world_snapshot=world_snapshots[state["index"]],
            agent=agent,
        )
        if state["index"] == 0:
            state["index"] = 1
        await nc.publish(_RESPONSES_SUBJECT, response.model_dump_json().encode("utf-8"))

    sub = await nc.subscribe(_INTENTS_SUBJECT, cb=handler)
    try:
        await stop_event.wait()
    finally:
        await sub.unsubscribe()
        await nc.drain()
        await nc.close()


async def _main() -> None:
    os.environ["QIKI_RESPONSES_SUBJECT"] = _RESPONSES_SUBJECT
    orion_v_app_module.QIKI_INTENTS = _INTENTS_SUBJECT

    stop_event = asyncio.Event()
    responder_task = asyncio.create_task(_hostile_intent_responder(stop_event))
    try:
        app = OrionVApp()
        async with app.run_test(size=(160, 48)) as pilot:
            await _wait_until(
                lambda: app._nats_client.connection_state == "connected",
                timeout_s=10.0,
                step_s=0.1,
                label="NATS connection",
            )
            await _wait_until(
                lambda: isinstance(app._telemetry.get("sim_state"), dict),
                timeout_s=10.0,
                step_s=0.1,
                label="sim_state telemetry",
            )
            await pilot.pause()

            app._qiki_last_response = None
            await app._publish_qiki_intent(_COMMAND_TEXT)
            await _wait_until(
                lambda: app._qiki_last_response is not None,
                timeout_s=5.0,
                step_s=0.05,
                label="hostile-intent blocked response",
            )
            await pilot.pause()

            blocked_response = app._qiki_last_response
            assert blocked_response is not None
            assert blocked_response.legality is not None
            assert blocked_response.legality.status == "blocked"
            assert blocked_response.legality.domain == "protocol"
            assert blocked_response.legality.reason_code == _STATION_BLOCK_CODE
            assert blocked_response.reply is not None

            blocked_help = _widget_text(app.query_one("#orionv-help", Static))
            blocked_body = _widget_text(app.query_one("#orionv-cockpit-body", Static))

            assert blocked_help.startswith("QIKI blocked:"), blocked_help
            assert _STATION_BLOCK_CODE in blocked_help, blocked_help
            assert "Статус/Status: blocked [protocol] STATION_COMBAT_PROTOCOL_BLOCK" in blocked_body
            assert "Следующий шаг/Next:" in blocked_body

            app._qiki_last_response = None
            await app._publish_qiki_intent(_COMMAND_TEXT)
            await _wait_until(
                lambda: app._qiki_last_response is not None,
                timeout_s=5.0,
                step_s=0.05,
                label="hostile-intent allowed response",
            )
            await pilot.pause()

            allowed_response = app._qiki_last_response
            assert allowed_response is not None
            assert allowed_response.legality is not None
            assert allowed_response.legality.status == "allowed"
            assert allowed_response.legality.domain == "protocol"
            assert allowed_response.legality.reason_code == _HOSTILE_CONTEXT_OPEN_CODE
            assert allowed_response.reply is not None

            allowed_help = _widget_text(app.query_one("#orionv-help", Static))
            allowed_body = _widget_text(app.query_one("#orionv-cockpit-body", Static))

            assert allowed_help.startswith("QIKI allowed:"), allowed_help
            assert _HOSTILE_CONTEXT_OPEN_CODE in allowed_help, allowed_help
            assert f"Статус/Status: allowed [protocol] {_HOSTILE_CONTEXT_OPEN_CODE}" in allowed_body
            assert "классифицирована как FOE" in allowed_body
            assert "combat-entry" in allowed_body

            print("OK: orion_v_qiki_hostile_intent_smoke")
            print(f"BLOCKED_HELP={blocked_help}")
            print(f"BLOCKED_REPLY_RU={blocked_response.reply.body.ru}")
            print(f"ALLOWED_HELP={allowed_help}")
            print(f"ALLOWED_REPLY_RU={allowed_response.reply.body.ru}")
            print(f"BLOCKED_CODE={_STATION_BLOCK_CODE}")
            print(f"ALLOWED_CODE={_HOSTILE_CONTEXT_OPEN_CODE}")
    finally:
        stop_event.set()
        await responder_task


if __name__ == "__main__":
    asyncio.run(_main())
