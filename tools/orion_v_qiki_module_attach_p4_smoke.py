"""P4 live-proof (ADR-0019): параметризованная установка — полный цикл + негативы.

Живой контур: реальная шина, живой policy, живой конвейер тела, реальный
EVENTS_AUDIT. Сценарии:
1) антенна → F03: полный цикл, модуль на грани, леджер списан;
2) повторная антенна: policy разрешает (статический остаток), консоль
   блокирует ЛЕДЖЕРОМ [MODULE_DEPLETED] — fail-closed на исполнении;
3) rcs-кластер (запрещённый класс): approve проходит, ТЕЛО отказывает через
   конвейер (правда у тела), effect failed, свой аудит;
4) битый паспорт: канонный отказ конвейера;
5) занятое гнездо F03: отказ через конвейер (без шортката);
6) deferred-окно: предусловия ИНЪЕЦИРОВАНЫ (load_shedding=true — прототипная
   инъекция снапшота, помечено) → мост не пускает, коды в аудит.
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
from qiki.shared.nats_connect import nats_auth_kwargs
from qiki.shared.nats_subjects import EVENTS_AUDIT

HEALTHY = {
    "power": {"soc_pct": 80, "supercap_soc_pct": 90, "bus_v": 28.0, "bus_a": 3.0,
              "load_shedding": False, "pdu_throttled": False},
    "thermal": {"nodes": [
        {"id": "T_core", "temp_c": 25.0, "warned": False, "tripped": False},
        {"id": "T_pdu", "temp_c": 30.0, "warned": False, "tripped": False},
    ]},
}


async def _wait_until(predicate, *, timeout_s: float, label: str) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"timeout: {label}")


async def _ask_and_confirm(app, text: str, *, healthy: bool = True) -> None:
    app._qiki_pending_action = None
    await app._publish_qiki_intent(text)
    await _wait_until(lambda: app._qiki_pending_action is not None, timeout_s=10.0,
                      label=f"candidate for '{text}'")
    if healthy:
        app._snapshot.update(HEALTHY)
    else:
        unhealthy = json.loads(json.dumps(HEALTHY))
        unhealthy["power"]["load_shedding"] = True
        app._snapshot.update(unhealthy)
    app._confirm_qiki_pending_action()


async def _main() -> None:
    import nats

    nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
    traces: list[dict[str, Any]] = []
    audit_nc = await nats.connect(servers=[nats_url], connect_timeout=3, allow_reconnect=False,
                                  **nats_auth_kwargs())

    async def _handler(msg) -> None:
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if isinstance(payload, dict) and payload.get("kind_event") == "qiki_body_attach_decision":
            traces.append(payload)

    sub = await audit_nc.subscribe(EVENTS_AUDIT, cb=_handler)
    reset_body_structure_interactive_state()
    app = OrionVApp()
    try:
        async with app.run_test(size=(180, 46)):
            await _wait_until(lambda: app._nats_client.connection_state == "connected",
                              timeout_s=10.0, label="NATS")
            app.push_screen = lambda screen, callback=None: callback and callback(True)  # type: ignore

            # 1) антенна -> F03: полный цикл
            await _ask_and_confirm(app, "установи антенну на F03")
            await _wait_until(lambda: traces, timeout_s=10.0, label="trace #1")
            body = get_body_structure_interactive_controller().snapshot().body
            installed = [str(m.get("module_id")) for m in body.modules]
            assert installed == ["comm_antenna_module_001"], installed
            assert traces[-1]["runtime_claim_status"] == "runtime_effect_confirmed"
            assert app._cargo_spent.get("comm_antenna_module_001") == 1
            print("[smoke] 1: антенна установлена на F03 живьём; леджер: потрачен 1/1")

            # 2) повторная антенна: леджер блокирует исполнение
            await _ask_and_confirm(app, "установи антенну на F05")
            await asyncio.sleep(0.3)
            assert app._qiki_last_response.consequence.status == "not_sent"
            assert "MODULE_DEPLETED" in app._qiki_last_response.consequence.summary.ru
            assert len(get_body_structure_interactive_controller().snapshot().body.modules) == 1
            print("[smoke] 2: повторная антенна -> MODULE_DEPLETED леджером, тело не тронуто")

            # 3) запрещённый класс: правда у тела
            before = len(traces)
            await _ask_and_confirm(app, "установи rcs_cluster_module_001 на F02")
            await _wait_until(lambda: len(traces) > before, timeout_s=10.0, label="trace #3")
            assert app._qiki_last_response.consequence.status == "failed"
            assert len(get_body_structure_interactive_controller().snapshot().body.modules) == 1
            print("[smoke] 3: rcs-кластер отклонён ТЕЛОМ (класс запрещён), effect failed, аудит свой")

            # 4) битый паспорт
            before = len(traces)
            await _ask_and_confirm(app, "установи salvage_sensor_damaged_001 на F01")
            await _wait_until(lambda: len(traces) > before, timeout_s=10.0, label="trace #4")
            assert app._qiki_last_response.consequence.status == "failed"
            print("[smoke] 4: битый манифест -> канонный отказ конвейера (паспорт не собран)")

            # 5) занятое гнездо F03 — через конвейер, без шортката
            before = len(traces)
            await _ask_and_confirm(app, "установи test_sensor_module_001 на F03")
            await _wait_until(lambda: len(traces) > before, timeout_s=10.0, label="trace #5")
            assert app._qiki_last_response.consequence.status == "failed"
            assert len(get_body_structure_interactive_controller().snapshot().body.modules) == 1
            print("[smoke] 5: F03 занято антенной -> отказ через конвейер, свой аудит")

            # 6) deferred-окно (предусловия ИНЪЕЦИРОВАНЫ: load_shedding=true)
            before = len(traces)
            await _ask_and_confirm(app, "установи test_sensor_module_001 на F04", healthy=False)
            await _wait_until(lambda: len(traces) > before, timeout_s=10.0, label="trace #6")
            assert traces[-1]["reached_body"] is False
            assert "BRIDGE_POWER_BLOCK" in traces[-1]["bridge_reason_codes"]
            assert len(get_body_structure_interactive_controller().snapshot().body.modules) == 1
            print("[smoke] 6: deferred-окно (инъекция load_shedding) -> мост не пустил, коды в аудите")

            print("[smoke] P4 LIVE PASS: параметризованный цикл + 5 негативов на живом контуре")
    finally:
        await sub.unsubscribe()
        await audit_nc.close()
        reset_body_structure_interactive_state()


if __name__ == "__main__":
    asyncio.run(_main())
