"""M7-M9 live-wiring proof: полный игровой цикл «q: установи модуль» → тело.

Живой контур целиком (ADR-0018):
1) реальная шина: intent уходит в qiki.intents, ЖИВОЙ policy-сервис отвечает
   BODY_ATTACH-кандидатом (M0c-регистрация request_id соблюдена);
2) approve (M6) + пломба/authorize (M5) в реальном app;
3) мост M7-M9 зовёт ЖИВОЙ конвейер тела (тот же, что клавиша B) —
   модуль установлен, решение PUBLISHED, effect=ok;
4) трасса решения уходит в РЕАЛЬНЫЙ аудит-стрим (EVENTS_AUDIT) и ловится
   отдельным NATS-подписчиком.

Предусловия: если живая телеметрия не даёт чистых power/thermal — smoke
показывает честный deferred с кодами и повторяет позитив на «здоровом»
снапшоте (fail-closed поведение тоже доказывается).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    get_body_structure_interactive_controller,
    reset_body_structure_interactive_state,
)
from qiki.shared.command_decision import DecisionStatus
from qiki.shared.nats_connect import nats_auth_kwargs
from qiki.shared.nats_subjects import EVENTS_AUDIT

HEALTHY_SNAPSHOT: dict[str, Any] = {
    "power": {
        "soc_pct": 80,
        "supercap_soc_pct": 90,
        "bus_v": 28.0,
        "bus_a": 3.0,
        "load_shedding": False,
        "pdu_throttled": False,
    },
    "thermal": {
        "nodes": [
            {"id": "T_core", "temp_c": 25.0, "warned": False, "tripped": False},
            {"id": "T_pdu", "temp_c": 30.0, "warned": False, "tripped": False},
        ]
    },
}


async def _wait_until(predicate, *, timeout_s: float, label: str) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"timeout while waiting for {label}")


async def _main() -> None:
    import nats

    nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
    audit_events: list[dict[str, Any]] = []

    audit_nc = await nats.connect(
        servers=[nats_url], connect_timeout=3, allow_reconnect=False, **nats_auth_kwargs()
    )

    async def _audit_handler(msg) -> None:
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if isinstance(payload, dict) and payload.get("kind_event") == "qiki_body_attach_decision":
            audit_events.append(payload)

    audit_sub = await audit_nc.subscribe(EVENTS_AUDIT, cb=_audit_handler)

    reset_body_structure_interactive_state()
    app = OrionVApp()
    try:
        async with app.run_test(size=(180, 46)) as pilot:
            await _wait_until(
                lambda: app._nats_client.connection_state == "connected",
                timeout_s=10.0,
                label="console NATS connection",
            )

            # 1) РЕАЛЬНЫЙ intent по шине — отвечает живой policy-сервис.
            await app._publish_qiki_intent("установи модуль")
            await _wait_until(
                lambda: app._qiki_pending_action is not None,
                timeout_s=10.0,
                label="live BODY_ATTACH candidate from policy service",
            )
            action = dict(app._qiki_pending_action or {})
            assert action.get("action_kind") == "BODY_ATTACH", action
            assert action.get("name") == "attach.module", action
            legality = app._qiki_last_response.legality
            assert legality is not None and legality.status == "allowed", legality
            print("[smoke] живой BODY_ATTACH-кандидат получен по шине "
                  f"(mount={action['parameters'].get('mount')}, module={action['parameters'].get('module_id')})")

            # 2) Approve (M6) с авто-подтверждением диалога (B1-диалог не тестируем здесь).
            app.push_screen = lambda screen, callback=None: callback and callback(True)  # type: ignore

            # 2а) Предусловия живой телеметрии; при блоке — честный deferred, затем позитив.
            power_blocked, thermal_blocked, detail = app._body_attach_preconditions()
            if power_blocked or thermal_blocked:
                app._confirm_qiki_pending_action()
                await _wait_until(lambda: audit_events, timeout_s=10.0, label="deferred trace in audit")
                trace = audit_events[-1]
                assert trace["reached_body"] is False
                assert trace["runtime_claim_status"] == "runtime_command_pending"
                print(f"[smoke] fail-closed доказан живьём: deferred {list(detail)} "
                      f"codes={trace['bridge_reason_codes']}")
                # повторный заход на здоровом снапшоте
                await app._publish_qiki_intent("установи модуль")
                await _wait_until(
                    lambda: app._qiki_pending_action is not None,
                    timeout_s=10.0,
                    label="second live candidate",
                )
                app._snapshot.update(HEALTHY_SNAPSHOT)
            else:
                print("[smoke] живые предусловия чисты (power/thermal green)")

            audit_before = len(audit_events)
            app._confirm_qiki_pending_action()
            await _wait_until(
                lambda: len(audit_events) > audit_before,
                timeout_s=10.0,
                label="attach trace in real audit stream",
            )

            # 3) Тело: живой конвейер установил модуль.
            snapshot = get_body_structure_interactive_controller().snapshot()
            assert str(snapshot.interaction_state) == "attached", snapshot.interaction_state
            assert snapshot.after_modules_count == snapshot.before_modules_count + 1

            # 4) Решение: PUBLISHED, ступени не схлопнуты, effect/audit ok.
            decision = app._decision_store.get(app._pending_decision_id)
            assert decision is not None and decision.status is DecisionStatus.PUBLISHED
            assert decision.stages.effect.value == "ok", decision.stages
            assert decision.stages.audit.value == "ok", decision.stages

            trace = audit_events[-1]
            assert trace["runtime_claim_status"] == "runtime_effect_confirmed"
            assert trace["stages"]["effect"] == "ok"
            print("[smoke] мост→тело живьём: модуль установлен, decision PUBLISHED, "
                  f"stages ack={trace['stages']['ack']} effect={trace['stages']['effect']} "
                  f"audit={trace['stages']['audit']}")
            print("[smoke] трасса поймана в РЕАЛЬНОМ аудит-стриме "
                  f"(runtime_claim_status={trace['runtime_claim_status']})")
            print("[smoke] M7-M9 LIVE PASS: полный цикл intent→candidate→approve→мост→тело→аудит")
    finally:
        await audit_sub.unsubscribe()
        await audit_nc.close()
        reset_body_structure_interactive_state()


if __name__ == "__main__":
    asyncio.run(_main())
