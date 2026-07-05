"""Live-proof процедурной установки (ADR-0019 P4 + ADR-0020 P1).

Живой контур: реальная шина, живой policy, живой конвейер тела, реальный
EVENTS_AUDIT. Сценарии:
1) антенна → F03: зелёные стадии авто-проходят, модуль на грани, леджер списан;
2) повторная антенна: леджер блокирует исполнение [MODULE_DEPLETED];
3) rcs-кластер (запрещённый класс): правда у тела — отказ конвейера на S5;
4) битый паспорт: РАЗВИЛКА S2 (процедура ждёт оператора) → resume без
   паспорта → канонный отказ конвейера;
5) занятое гнездо: ранний abort осмотром S1 [MOUNT_POINT_OCCUPIED];
6) deferred-окно (инъекция load_shedding, помечено) → hold → «остывание» →
   resume → установлен: hold-окно прожито живьём.
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


async def _ask_and_confirm(app, text: str) -> None:
    app._qiki_pending_action = None
    await app._publish_qiki_intent(text)
    await _wait_until(lambda: app._qiki_pending_action is not None, timeout_s=10.0,
                      label=f"candidate for '{text}'")
    # P2: предусловия и тики питает ЖИВАЯ телеметрия; снапшот не инъецируем
    app._confirm_qiki_pending_action()


async def _main() -> None:
    import nats

    nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
    traces: list[dict[str, Any]] = []
    stage_events: list[dict[str, Any]] = []
    audit_nc = await nats.connect(servers=[nats_url], connect_timeout=3, allow_reconnect=False,
                                  **nats_auth_kwargs())

    async def _handler(msg) -> None:
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        if payload.get("kind_event") == "qiki_body_attach_decision":
            traces.append(payload)
        elif payload.get("kind_event") == "qiki_attach_stage":
            stage_events.append(payload)

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
            await _wait_until(lambda: traces, timeout_s=20.0, label="trace #1 (живые тики переноса)")
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
            await _wait_until(lambda: len(traces) > before, timeout_s=20.0, label="trace #3")
            assert app._qiki_last_response.consequence.status == "failed"
            assert len(get_body_structure_interactive_controller().snapshot().body.modules) == 1
            print("[smoke] 3: rcs-кластер отклонён ТЕЛОМ (класс запрещён), effect failed, аудит свой")

            # 4) битый паспорт: развилка S2 (ADR-0020) -> оператор продолжает без паспорта
            before = len(traces)
            await _ask_and_confirm(app, "установи salvage_sensor_damaged_001 на F01")
            await _wait_until(
                lambda: app._attach_procedure is not None
                and app._attach_procedure.complication == "PASSPORT_DAMAGED",
                timeout_s=10.0, label="S2 fork #4",
            )
            print("[smoke] 4a: развилка S2 — манифест повреждён, процедура ждёт оператора")
            await app._resume_attach_procedure()
            await _wait_until(lambda: len(traces) > before, timeout_s=20.0, label="trace #4")
            assert app._attach_procedure.status == "failed"
            print("[smoke] 4b: продолжено без паспорта -> канонный отказ конвейера")

            # 5) занятое гнездо F03 — ранний abort осмотром S1 (нон-авторитетное чтение)
            await _ask_and_confirm(app, "установи test_sensor_module_001 на F03")
            await _wait_until(
                lambda: app._attach_procedure is not None
                and app._attach_procedure.status == "aborted",
                timeout_s=10.0, label="S1 abort #5",
            )
            assert app._attach_procedure.complication == "MOUNT_POINT_OCCUPIED"
            assert len(get_body_structure_interactive_controller().snapshot().body.modules) == 1
            print("[smoke] 5: F03 занято антенной -> осмотр S1 прервал рано [MOUNT_POINT_OCCUPIED]")

            # 6) deferred-окно: предусловие ИНЪЕЦИРОВАНО методом (помечено в аудите)
            original_preconditions = app._body_attach_preconditions
            app._body_attach_preconditions = lambda: (True, False, ("load_shedding_injected",))  # type: ignore
            await _ask_and_confirm(app, "установи test_sensor_module_001 на F04")
            await _wait_until(
                lambda: app._attach_procedure is not None
                and app._attach_procedure.status == "holding",
                timeout_s=15.0, label="holding #6",
            )
            assert any(
                "load_shedding_injected" in (e.get("reason_codes") or []) for e in stage_events
            ), stage_events[-3:]
            assert len(get_body_structure_interactive_controller().snapshot().body.modules) == 1
            print("[smoke] 6a: окно закрыто (инъекция предусловия) -> процедура в hold, коды в аудите")
            app._body_attach_preconditions = original_preconditions  # type: ignore  # «остыло»
            await app._resume_attach_procedure()
            await _wait_until(
                lambda: app._attach_procedure is not None and app._attach_procedure.status == "done",
                timeout_s=20.0, label="resume done #6",
            )
            assert len(get_body_structure_interactive_controller().snapshot().body.modules) == 2
            print("[smoke] 6b: resume после остывания -> модуль установлен (hold-окно прожито живьём)")

            print("[smoke] P4 LIVE PASS: процедурный цикл ADR-0020 + развилки/hold на живом контуре")
    finally:
        await sub.unsubscribe()
        await audit_nc.close()
        reset_body_structure_interactive_state()


if __name__ == "__main__":
    asyncio.run(_main())
