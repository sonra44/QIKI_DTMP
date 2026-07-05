"""P2 (ADR-0020): время S3 — тики, пауза мира, окно посреди переноса, hold.

RED первым: пауза мира замораживает процедуру (тик = снапшот с paused=false);
per-грань длительность; окно, закрывшееся посреди переноса, — операторская
развилка (авто-resume запрещён); q hold/resume на протяжённой стадии.
"""

from __future__ import annotations

import asyncio

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.attach_procedure import (
    STAGE_S3_TRANSFER,
    STATUS_DONE,
    STATUS_HOLDING,
    STATUS_RUNNING,
    transfer_ticks_for_mount,
)
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
    "sim_state": {"paused": False, "fsm_state": "RUNNING"},
}


def _action(mount="F01") -> dict:
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
            "passport_damaged": False,
        },
        "dry_run": False,
    }


def _app() -> tuple[OrionVApp, dict]:
    calls = {"audit": [], "help": []}
    app = OrionVApp()
    app._snapshot = {k: (dict(v) if isinstance(v, dict) else v) for k, v in HEALTHY.items()}
    app._set_help_text = lambda text="", *a, **k: calls["help"].append(str(text))  # type: ignore
    app._set_last_command_loop_state = lambda *a, **k: None  # type: ignore
    app._request_refresh_ui = lambda: None  # type: ignore

    async def _audit(subject: str, payload: dict) -> None:
        calls["audit"].append((subject, payload))

    app._publish_audit_event = _audit  # type: ignore
    return app, calls


def _start(app: OrionVApp, mount="F01") -> None:
    action = _action(mount)
    app._qiki_pending_action = dict(action)
    app._seal_pending_decision(action)
    asyncio.run(app._execute_qiki_pending_action())


def _tick(app: OrionVApp, *, paused=False, load_shedding=False) -> None:
    app._snapshot["sim_state"] = {"paused": paused, "fsm_state": "PAUSED" if paused else "RUNNING"}
    app._snapshot["power"] = {**HEALTHY["power"], "load_shedding": load_shedding}
    app._attach_procedure_on_snapshot()


def setup_function() -> None:
    reset_body_structure_interactive_state()


def teardown_function() -> None:
    reset_body_structure_interactive_state()


def test_red_transfer_waits_ticks_and_completes() -> None:
    app, _ = _app()
    _start(app, mount="F01")
    proc = app._attach_procedure
    assert proc.stage == STAGE_S3_TRANSFER and proc.status == STATUS_RUNNING
    assert proc.ticks_required == transfer_ticks_for_mount("F01")
    assert get_body_structure_interactive_controller().snapshot().body.modules == ()
    for _ in range(proc.ticks_required):
        _tick(app)
    asyncio.run(asyncio.sleep(0))  # добить создание финальной задачи
    assert app._attach_procedure.status == STATUS_DONE
    assert len(get_body_structure_interactive_controller().snapshot().body.modules) == 1


def test_red_far_mount_takes_longer() -> None:
    assert transfer_ticks_for_mount("F01") < transfer_ticks_for_mount("F09")


def test_red_world_pause_freezes_transfer() -> None:
    """Тик = снапшот с paused=false; пауза мира — авто-hold WORLD_PAUSED."""
    app, _ = _app()
    _start(app, mount="F09")
    _tick(app)  # 1 честный тик
    ticks_before = app._attach_procedure.ticks_done
    _tick(app, paused=True)
    proc = app._attach_procedure
    assert proc.ticks_done == ticks_before  # время не шло
    assert proc.status == STATUS_HOLDING and proc.complication == "WORLD_PAUSED"
    # мир пошёл — авто-resume (это не операторская развилка)
    _tick(app)
    assert app._attach_procedure.status == STATUS_RUNNING
    assert app._attach_procedure.ticks_done == ticks_before + 1


def test_red_window_close_mid_transfer_is_operator_fork() -> None:
    """Окно закрылось посреди S3 — операторская развилка: авто-resume ЗАПРЕЩЁН."""
    app, _ = _app()
    _start(app, mount="F09")
    _tick(app, load_shedding=True)
    proc = app._attach_procedure
    assert proc.status == STATUS_HOLDING
    assert "load_shedding" in proc.complication
    ticks = proc.ticks_done
    # чистый снапшот НЕ продолжает сам — решает оператор
    _tick(app)
    assert app._attach_procedure.status == STATUS_HOLDING
    assert app._attach_procedure.ticks_done == ticks
    # оператор продолжил
    asyncio.run(app._resume_attach_procedure())
    assert app._attach_procedure.status == STATUS_RUNNING
    _tick(app)
    assert app._attach_procedure.ticks_done == ticks + 1


def test_red_operator_hold_and_resume_on_transfer() -> None:
    app, _ = _app()
    _start(app, mount="F09")
    _tick(app)
    app._hold_attach_procedure()
    proc = app._attach_procedure
    assert proc.status == STATUS_HOLDING and proc.complication == "OPERATOR_HOLD"
    ticks = proc.ticks_done
    _tick(app)
    assert app._attach_procedure.ticks_done == ticks  # пауза держит
    asyncio.run(app._resume_attach_procedure())
    assert app._attach_procedure.status == STATUS_RUNNING
    _tick(app)
    assert app._attach_procedure.ticks_done == ticks + 1


def test_red_telem_stale_auto_holds_and_recovers() -> None:
    app, _ = _app()
    _start(app, mount="F09")
    _tick(app)
    app._last_telemetry_received_wall = 0.0  # телеметрия «мертва» давно
    app._attach_procedure_stale_check()
    proc = app._attach_procedure
    assert proc.status == STATUS_HOLDING and proc.complication == "TELEM_STALE"
    ticks = proc.ticks_done
    # пришёл живой снапшот — авто-восстановление и тик
    _tick(app)
    assert app._attach_procedure.status == STATUS_RUNNING
    assert app._attach_procedure.ticks_done == ticks + 1


def test_abort_during_transfer_leaves_body_untouched() -> None:
    app, _ = _app()
    _start(app, mount="F09")
    _tick(app)
    app._abort_attach_procedure()
    assert app._attach_procedure.status == "aborted"
    assert get_body_structure_interactive_controller().snapshot().body.modules == ()
    assert app._cargo_spent == {}
