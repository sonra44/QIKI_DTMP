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

_INTENTS_SUBJECT = "qiki.intents.g2resource"
_RESPONSES_SUBJECT = "qiki.responses.qiki.g2resource"
_COMMAND_TEXT = "attack object UNBT9999"
_RESOURCE_BLOCK_CODE = "COMBAT_ENTRY_RCS_RESOURCE_LOW"
_READY_CODE = "COMBAT_ENTRY_PROCEDURE_READY"


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


async def _hostile_resource_responder(stop_event: asyncio.Event) -> None:
    world_snapshots = [
        {
            "radar_tracks": [
                {
                    "object_type": 2,
                    "range_m": 2200.0,
                    "quality": 0.95,
                    "age_s": 0.1,
                    "transponder_id": "UNBT9999",
                    "iff": 2,
                }
            ],
            "propulsion": {"rcs": {"enabled": True, "propellant_kg": 0.6}},
        },
        {
            "radar_tracks": [
                {
                    "object_type": 2,
                    "range_m": 2200.0,
                    "quality": 0.95,
                    "age_s": 0.1,
                    "transponder_id": "UNBT9999",
                    "iff": 2,
                }
            ],
            "propulsion": {"rcs": {"enabled": True, "propellant_kg": 12.0}},
        },
    ]
    agent = SimpleNamespace(context=SimpleNamespace(qiki_repeat_state={}))
    state = {"index": 0}
    nc = await nats.connect(
        servers=[os.getenv("NATS_URL", "nats://nats:4222")],
        connect_timeout=3,
        allow_reconnect=False,
        max_reconnect_attempts=0,
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
    responder_task = asyncio.create_task(_hostile_resource_responder(stop_event))
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
                label="resource blocked response",
            )
            await pilot.pause()

            blocked_response = app._qiki_last_response
            assert blocked_response is not None
            assert blocked_response.legality is not None
            assert blocked_response.legality.status == "blocked"
            assert blocked_response.legality.domain == "resource"
            assert blocked_response.legality.reason_code == _RESOURCE_BLOCK_CODE
            blocked_help = _widget_text(app.query_one("#orionv-help", Static))
            blocked_body = _widget_text(app.query_one("#orionv-cockpit-body", Static))
            assert blocked_help.startswith("QIKI blocked:"), blocked_help
            assert _RESOURCE_BLOCK_CODE in blocked_help, blocked_help
            assert "Статус/Status: blocked [resource] COMBAT_ENTRY_RCS_RESOURCE_LOW" in blocked_body

            app._qiki_last_response = None
            await app._publish_qiki_intent(_COMMAND_TEXT)
            await _wait_until(
                lambda: app._qiki_last_response is not None,
                timeout_s=5.0,
                step_s=0.05,
                label="resource allow response",
            )
            await pilot.pause()

            allowed_response = app._qiki_last_response
            assert allowed_response is not None
            assert allowed_response.legality is not None
            assert allowed_response.legality.status == "allowed"
            assert allowed_response.legality.reason_code == _READY_CODE
            allowed_help = _widget_text(app.query_one("#orionv-help", Static))
            allowed_body = _widget_text(app.query_one("#orionv-cockpit-body", Static))
            assert allowed_help.startswith("QIKI allowed:"), allowed_help
            assert _READY_CODE in allowed_help, allowed_help
            assert "Статус/Status: allowed [protocol] COMBAT_ENTRY_PROCEDURE_READY" in allowed_body

            print("OK: orion_v_qiki_hostile_resource_gate_smoke")
            print(f"RESOURCE_BLOCK_HELP={blocked_help}")
            print(f"RESOURCE_BLOCK_REPLY_RU={blocked_response.reply.body.ru}")
            print(f"ALLOWED_HELP={allowed_help}")
            print(f"ALLOWED_REPLY_RU={allowed_response.reply.body.ru}")
            print(f"BLOCKED_CODE={_RESOURCE_BLOCK_CODE}")
            print(f"ALLOWED_CODE={_READY_CODE}")
    finally:
        stop_event.set()
        await responder_task


if __name__ == "__main__":
    asyncio.run(_main())
