"""Срез 2 (F5-эхо): исход установки возвращается в ленту ГОЛОСОМ QIKI.

До среза лента при исходе получала только машинные стадии ПРОЦЕДУРЫ
(«S5 стыковка: … установлен») — реплики QIKI не было. Теперь исход
(done/failed) добавляет запись в _qiki_voice_ledger: ACK при успехе,
REJECT при отказе конвейера. ПРОЦЕДУРА-леджер не трогаем (ADR-0020 §6:
это разные говорящие).
"""

from __future__ import annotations

import asyncio

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.attach_procedure import (
    STATUS_AWAITING,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_HOLDING,
)
from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    reset_body_structure_interactive_state,
)

HEALTHY = {
    "power": {"soc_pct": 80, "supercap_soc_pct": 90, "bus_v": 28.0, "bus_a": 3.0,
              "load_shedding": False, "pdu_throttled": False},
    "thermal": {"nodes": [
        {"id": "T_core", "temp_c": 25.0, "warned": False, "tripped": False},
    ]},
    "sim_state": {"paused": False, "fsm_state": "RUNNING"},
}


def _action(mount="F01", *, passport_damaged=False) -> dict:
    return {
        "action_kind": "BODY_ATTACH",
        "title_ru": "Установка",
        "subject": "orionv.body",
        "name": "attach.module",
        "parameters": {
            "module_id": "test_sensor_module_001",
            "mount": mount,
            "module_class": "sensor",
            "provided_capabilities": ["basic_sensor_read"],
            "quantity": 2,
            "passport_damaged": passport_damaged,
        },
        "dry_run": False,
    }


def _app() -> OrionVApp:
    app = OrionVApp()
    app._snapshot = {k: (dict(v) if isinstance(v, dict) else v) for k, v in HEALTHY.items()}
    app._set_help_text = lambda text="", *a, **k: None  # type: ignore
    app._set_last_command_loop_state = lambda *a, **k: None  # type: ignore
    app._request_refresh_ui = lambda: None  # type: ignore

    async def _audit(subject: str, payload: dict) -> None:
        return None

    app._publish_audit_event = _audit  # type: ignore
    return app


def _run_to_outcome(app: OrionVApp, action: dict) -> None:
    app._qiki_pending_action = dict(action)
    app._seal_pending_decision(action)
    asyncio.run(app._execute_qiki_pending_action())
    proc = app._attach_procedure
    for _ in range(proc.ticks_required + 2):
        if proc.status not in {STATUS_DONE, STATUS_FAILED, STATUS_HOLDING}:
            app._attach_procedure_on_snapshot()
    asyncio.run(asyncio.sleep(0))  # добить финальную задачу


def setup_function() -> None:
    reset_body_structure_interactive_state()


def teardown_function() -> None:
    reset_body_structure_interactive_state()


def test_done_echoes_ack_voice_reply() -> None:
    """Успех: в ленту падает реплика QIKI (ACK) с человеческим текстом."""
    app = _app()
    _run_to_outcome(app, _action("F01"))
    assert app._attach_procedure.status == STATUS_DONE
    entries = list(app._qiki_voice_ledger)
    assert entries, "исход должен породить реплику QIKI в леджере голоса"
    echo = entries[-1]
    assert echo.kind == "ACK"
    assert "test_sensor_module_001" in echo.text
    assert "F01" in echo.text  # оператор видит ГДЕ
    assert "S5" not in echo.text  # человеческая речь, не машинная стадия


def test_failed_echoes_reject_voice_reply() -> None:
    """Отказ конвейера (без паспорта): реплика QIKI REJECT с причиной."""
    app = _app()
    action = _action("F01", passport_damaged=True)
    app._qiki_pending_action = dict(action)
    app._seal_pending_decision(action)
    asyncio.run(app._execute_qiki_pending_action())
    proc = app._attach_procedure
    assert proc.status == STATUS_AWAITING and proc.complication == "PASSPORT_DAMAGED"
    # Оператор осознанно продолжает без паспорта — исход решает конвейер.
    asyncio.run(app._resume_attach_procedure())
    for _ in range(proc.ticks_required + 2):
        if proc.status not in {STATUS_DONE, STATUS_FAILED}:
            app._attach_procedure_on_snapshot()
    asyncio.run(asyncio.sleep(0))
    assert proc.status == STATUS_FAILED
    entries = list(app._qiki_voice_ledger)
    assert entries, "отказ тоже должен вернуться голосом QIKI"
    echo = entries[-1]
    assert echo.kind == "REJECT"
    assert "не" in echo.text.lower() or "отказ" in echo.text.lower()


def test_stage_notes_still_go_to_procedure_ledger() -> None:
    """ПРОЦЕДУРА-леджер не подменяется эхом: машинные стадии остаются отдельно."""
    app = _app()
    _run_to_outcome(app, _action("F01"))
    stages = [text for _, text in app._attach_procedure_ledger]
    assert any("S5" in s for s in stages)  # машинный след жив
