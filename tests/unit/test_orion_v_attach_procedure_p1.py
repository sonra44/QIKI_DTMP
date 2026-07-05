"""P1 (ADR-0020): AttachProcedure — захват решения, развилка S2, гейты, кнопка.

RED первым (ADR-0020 Roadmap P1):
(а) новый кандидат посреди процедуры НЕ меняет её пломбу;
(б) abort на S2 — тело не тронуто, леджер цел;
плюс гейты PROCEDURE_BUSY (второй attach, клавиша B) и PROCEDURE_ACTIVE (R).
"""

from __future__ import annotations

import asyncio

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    get_body_structure_interactive_controller,
    reset_body_structure_interactive_state,
)

HEALTHY = {
    "power": {"soc_pct": 80, "supercap_soc_pct": 90, "bus_v": 28.0, "bus_a": 3.0,
              "load_shedding": False, "pdu_throttled": False},
    "thermal": {"nodes": [
        {"id": "T_core", "temp_c": 25.0, "warned": False, "tripped": False},
    ]},
}


def _action(module_id="salvage_sensor_damaged_001", mount="F01", *, damaged=True,
            module_class="sensor", caps=()) -> dict:
    return {
        "action_kind": "BODY_ATTACH",
        "title_ru": "Установка",
        "subject": "orionv.body",
        "name": "attach.module",
        "parameters": {
            "module_id": module_id,
            "mount": mount,
            "module_class": module_class,
            "provided_capabilities": list(caps),
            "quantity": 1,
            "passport_damaged": damaged,
        },
        "dry_run": False,
    }


def _app() -> tuple[OrionVApp, dict]:
    calls = {"audit": [], "help": []}
    app = OrionVApp()
    app._snapshot = dict(HEALTHY)
    app._set_help_text = lambda text="", *a, **k: calls["help"].append(str(text))  # type: ignore
    app._set_last_command_loop_state = lambda *a, **k: None  # type: ignore
    app._request_refresh_ui = lambda: None  # type: ignore

    async def _audit(subject: str, payload: dict) -> None:
        calls["audit"].append((subject, payload))

    app._publish_audit_event = _audit  # type: ignore
    return app, calls


def _seal_and_start(app: OrionVApp, action: dict) -> None:
    app._qiki_pending_action = dict(action)
    app._seal_pending_decision(action)
    asyncio.run(app._execute_qiki_pending_action())


def setup_function() -> None:
    reset_body_structure_interactive_state()


def teardown_function() -> None:
    reset_body_structure_interactive_state()


def test_red_damaged_stops_at_s2_awaiting_operator() -> None:
    app, calls = _app()
    _seal_and_start(app, _action())
    proc = app._attach_procedure
    assert proc is not None and proc.status == "awaiting_operator"
    assert proc.complication == "PASSPORT_DAMAGED"
    assert get_body_structure_interactive_controller().snapshot().body.modules == ()
    stages = [p.get("stage") for _, p in calls["audit"] if p.get("kind_event") == "qiki_attach_stage"]
    assert "s2_prepare" in stages


def test_red_new_candidate_does_not_change_procedure_seal() -> None:
    """(а) Гонка C1: разговор с ботом посреди процедуры не подменяет пломбу."""
    app, _ = _app()
    _seal_and_start(app, _action())  # застряла на S2 (damaged)
    # Посторонний разговор: новый кандидат сбрасывает глобальную пломбу и пишет новую
    app._pending_decision_id = None
    app._qiki_pending_action = _action(module_id="comm_antenna_module_001", mount="F09",
                                       damaged=False, module_class="antenna")
    app._seal_pending_decision(app._qiki_pending_action)
    # Продолжаем процедуру (без паспорта) — тело должно получить ЗАХВАЧЕННЫЙ модуль
    asyncio.run(app._resume_attach_procedure())
    proc = app._attach_procedure
    assert proc is not None and proc.status == "failed"  # без паспорта конвейер отказал
    snap_decision = get_body_structure_interactive_controller().snapshot().decision
    assert snap_decision is not None
    requested = str(snap_decision.requested_module_id or snap_decision.module_id)
    assert requested == "salvage_sensor_damaged_001", requested  # НЕ антенна из новой пломбы
    assert get_body_structure_interactive_controller().snapshot().body.modules == ()


def test_red_abort_on_s2_body_untouched_ledger_intact() -> None:
    """(б) q abort на развилке: тело цело, леджер цел, аудит стадии есть."""
    app, calls = _app()
    _seal_and_start(app, _action())
    app._abort_attach_procedure()
    proc = app._attach_procedure
    assert proc is not None and proc.status == "aborted"
    assert get_body_structure_interactive_controller().snapshot().body.modules == ()
    assert app._cargo_spent == {}
    outcomes = [p.get("outcome") for _, p in calls["audit"] if p.get("kind_event") == "qiki_attach_stage"]
    assert "aborted" in outcomes


def test_procedure_busy_blocks_second_attach() -> None:
    app, calls = _app()
    _seal_and_start(app, _action())  # активна (awaiting_operator)
    app._qiki_pending_action = _action(module_id="test_sensor_module_001", damaged=False)
    app._seal_pending_decision(app._qiki_pending_action)
    asyncio.run(app._execute_qiki_pending_action())
    assert any("PROCEDURE_BUSY" in h for h in calls["help"])
    # процедура прежняя, на S2
    assert app._attach_procedure.complication == "PASSPORT_DAMAGED"


def test_b_key_blocked_during_procedure() -> None:
    app, calls = _app()
    _seal_and_start(app, _action())
    app.action_run_body_structure_self_check()
    assert any("PROCEDURE_BUSY" in h for h in calls["help"])
    assert get_body_structure_interactive_controller().snapshot().body.modules == ()


def test_r_key_blocked_during_procedure() -> None:
    app, calls = _app()
    _seal_and_start(app, _action())
    app.action_reset_body_structure_self_check()
    assert any("PROCEDURE_ACTIVE" in h for h in calls["help"])
    assert app._attach_procedure.status == "awaiting_operator"  # процедура жива


def test_green_clean_module_runs_to_done_and_spends_ledger() -> None:
    """Зелёный путь: авто-продвижение S1→S2→S5 без остановок, леджер списан."""
    app, calls = _app()
    _seal_and_start(app, _action(module_id="test_sensor_module_001", mount="F06",
                                 damaged=False, caps=("basic_sensor_read",)))
    proc = app._attach_procedure
    assert proc is not None and proc.status == "done"
    body = get_body_structure_interactive_controller().snapshot().body
    assert [str(m.get("module_id")) for m in body.modules] == ["test_sensor_module_001"]
    assert app._cargo_spent.get("test_sensor_module_001") == 1
    stages = [p.get("stage") for _, p in calls["audit"] if p.get("kind_event") == "qiki_attach_stage"]
    assert stages[:1] == ["s1_inspect"] and "s5_dock" in stages


def test_abort_after_done_is_too_late() -> None:
    app, calls = _app()
    _seal_and_start(app, _action(module_id="test_sensor_module_001", mount="F06",
                                 damaged=False, caps=("basic_sensor_read",)))
    assert app._attach_procedure.status == "done"
    app._abort_attach_procedure()
    assert any("ABORT_TOO_LATE" in h for h in calls["help"])
    assert app._attach_procedure.status == "done"  # статус не испорчен


def test_pause_start_button_state_plumbed() -> None:
    """Кнопка Пауза/Старт: состояние процедуры доезжает до state рейла."""
    from qiki.services.operator_console.orion_v.operator_state import build_operator_shell_state

    state = build_operator_shell_state(
        hardware_model=None,
        attach_procedure_active=True,
        attach_procedure_paused=True,
    )
    assert state.operator_loop.attach_procedure_active is True
    assert state.operator_loop.attach_procedure_paused is True
    idle = build_operator_shell_state(hardware_model=None)
    assert idle.operator_loop.attach_procedure_active is False
