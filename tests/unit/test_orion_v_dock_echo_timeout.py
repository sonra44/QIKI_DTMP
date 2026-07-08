"""Гигиена контура F5: эхо голосом QIKI для NATS-исходов (отстыковка),
эхо для прерванной установки, таймаут ожидания ответа QIKI.

- Все исходы возвращаются в ленту голосом QIKI (Срез 2 покрывал только attach).
- ABORTED больше не молчит.
- «awaiting_qiki» не висит вечно: просроченные запросы честно закрываются
  (QIKI НЕ отвечала — слова ей не вкладываем, это системный факт консоли).
"""

from __future__ import annotations

import asyncio
import time

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.attach_procedure import STATUS_ABORTED
from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    reset_body_structure_interactive_state,
)
from qiki.shared.models.qiki_chat import BilingualText

HEALTHY = {
    "power": {"soc_pct": 80, "supercap_soc_pct": 90, "bus_v": 28.0, "bus_a": 3.0,
              "load_shedding": False, "pdu_throttled": False},
    "thermal": {"nodes": [{"id": "T_core", "temp_c": 25.0, "warned": False, "tripped": False}]},
    "sim_state": {"paused": False, "fsm_state": "RUNNING"},
}


def _dock_action() -> dict:
    return {
        "action_kind": "NATS_COMMAND",
        "title_ru": "Подтвердить отстыковку",
        "subject": "qiki.commands.control",
        "name": "sim.dock.release",
        "parameters": {},
        "dry_run": False,
    }


def _attach_action(mount="F01") -> dict:
    return {
        "action_kind": "BODY_ATTACH",
        "title_ru": "Установка",
        "subject": "orionv.body",
        "name": "attach.module",
        "parameters": {"module_id": "test_sensor_module_001", "mount": mount,
                       "module_class": "sensor", "provided_capabilities": ["basic_sensor_read"],
                       "quantity": 2, "passport_damaged": False},
        "dry_run": False,
    }


def _app(*, ack=True, effect=True) -> OrionVApp:
    app = OrionVApp()
    app._snapshot = {k: (dict(v) if isinstance(v, dict) else v) for k, v in HEALTHY.items()}
    app._set_help_text = lambda text="", *a, **k: None  # type: ignore
    app._set_last_command_loop_state = lambda *a, **k: None  # type: ignore
    app._request_refresh_ui = lambda: None  # type: ignore

    async def _audit(subject, payload):
        return None

    async def _publish(command, parameters=None):
        return None

    async def _wait_ack(command, timeout):
        return ack

    async def _wait_effect(command, timeout):
        return BilingualText(en="undocked", ru="отстыковка подтверждена") if effect else None

    app._publish_audit_event = _audit  # type: ignore
    app._publish_sim_command = _publish  # type: ignore
    app._wait_for_ack = _wait_ack  # type: ignore
    app._wait_for_qiki_effect = _wait_effect  # type: ignore
    return app


def _run_pending(app: OrionVApp, action: dict) -> None:
    app._qiki_pending_action = dict(action)
    app._seal_pending_decision(action)
    asyncio.run(app._execute_qiki_pending_action())


def setup_function() -> None:
    reset_body_structure_interactive_state()


def teardown_function() -> None:
    reset_body_structure_interactive_state()


def test_dock_confirmed_echoes_ack_voice() -> None:
    """Подтверждённая отстыковка → реплика QIKI (ACK) в ленту."""
    app = _app(ack=True, effect=True)
    _run_pending(app, _dock_action())
    entries = list(app._qiki_voice_ledger)
    assert entries, "исход NATS-команды должен вернуться голосом QIKI"
    echo = entries[-1]
    assert echo.kind == "ACK"
    assert "sim.dock.release" in echo.text
    assert "подтверждён" in echo.text.lower()


def test_dock_ack_timeout_echoes_reject_voice() -> None:
    """Нет ACK → REJECT-реплика (команда не исполнена)."""
    app = _app(ack=False)
    _run_pending(app, _dock_action())
    echo = list(app._qiki_voice_ledger)[-1]
    assert echo.kind == "REJECT"
    assert "sim.dock.release" in echo.text


def test_dock_ack_without_effect_echoes_info_voice() -> None:
    """ACK есть, эффекта в телеметрии ещё нет → честный INFO (не ACK!)."""
    app = _app(ack=True, effect=False)
    _run_pending(app, _dock_action())
    echo = list(app._qiki_voice_ledger)[-1]
    assert echo.kind == "INFO"
    assert "телеметри" in echo.text.lower()


def test_aborted_attach_echoes_voice() -> None:
    """Прерванная установка больше не молчит голосом."""
    app = _app()
    action = _attach_action()
    app._qiki_pending_action = dict(action)
    app._seal_pending_decision(action)
    asyncio.run(app._execute_qiki_pending_action())
    assert app._attach_procedure is not None
    app._abort_attach_procedure()
    assert app._attach_procedure.status == STATUS_ABORTED
    echo = list(app._qiki_voice_ledger)[-1]
    assert "прерван" in echo.text.lower()
    assert "отсек" in echo.text.lower()  # модуль остался в отсеке


def test_expired_qiki_pending_is_closed_honestly() -> None:
    """«awaiting_qiki» не вечен: просроченный запрос закрывается со статусом."""
    states: list[tuple[str, str]] = []
    app = _app()
    app._set_last_command_loop_state = lambda s, t="": states.append((s, t))  # type: ignore
    app._qiki_pending["req-old"] = (time.time() - 999.0, "старый вопрос")
    app._qiki_pending["req-new"] = (time.time(), "свежий вопрос")
    app._expire_qiki_pending()
    assert "req-old" not in app._qiki_pending  # просрочен — закрыт
    assert "req-new" in app._qiki_pending  # свежий живёт
    assert any(s == "failed" for s, _ in states)
    # QIKI не отвечала — голос ей НЕ вкладываем (системный факт, не реплика)
    assert not any("старый вопрос" in e.text for e in app._qiki_voice_ledger)
