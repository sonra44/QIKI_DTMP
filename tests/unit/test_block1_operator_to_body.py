"""Блок 1 аудита «оператор→тело»: abort-гонка, TOCTOU пломбы, голые таски.

По карте AUDIT_2026-07-09_GLOBAL.md (HIGH).
"""

from __future__ import annotations

import asyncio
import logging

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.attach_procedure import STAGE_S4_POWER, STATUS_ABORTED
from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    get_body_structure_interactive_controller,
    reset_body_structure_interactive_state,
)
from qiki.shared.command_decision import CommandIntent, DecisionStatus, authorize_publish, seal_decision
from qiki.shared.decision_body_bridge import bridge_decision_to_body

HEALTHY = {
    "power": {"soc_pct": 80, "supercap_soc_pct": 90, "bus_v": 28.0, "bus_a": 3.0,
              "load_shedding": False, "pdu_throttled": False},
    "thermal": {"nodes": [{"id": "T_core", "temp_c": 25.0, "warned": False, "tripped": False}]},
    "sim_state": {"paused": False, "fsm_state": "RUNNING"},
}


def _action(mount="F01") -> dict:
    return {
        "action_kind": "BODY_ATTACH", "title_ru": "Установка", "subject": "orionv.body",
        "name": "attach.module",
        "parameters": {"module_id": "test_sensor_module_001", "mount": mount,
                       "module_class": "sensor", "provided_capabilities": ["basic_sensor_read"],
                       "quantity": 2, "passport_damaged": False},
        "dry_run": False,
    }


def setup_function() -> None:
    reset_body_structure_interactive_state()


def teardown_function() -> None:
    reset_body_structure_interactive_state()


# ── Фикс 1: abort во время await процедуры НЕ должен терять прерывание ──────

def test_abort_during_stage_audit_await_keeps_aborted_and_body_untouched() -> None:
    app = OrionVApp()
    app._snapshot = {k: (dict(v) if isinstance(v, dict) else v) for k, v in HEALTHY.items()}
    app._set_help_text = lambda *a, **k: None  # type: ignore
    app._set_last_command_loop_state = lambda *a, **k: None  # type: ignore
    app._request_refresh_ui = lambda: None  # type: ignore

    async def _audit_with_operator_abort(**kwargs):
        # эмуляция: оператор даёт q abort, пока корутина висит на публикации
        # аудита S4 «ok» — последний await перед S5-стыковкой (самое узкое окно)
        if kwargs.get("stage") == STAGE_S4_POWER and kwargs.get("outcome") == "ok":
            app._abort_attach_procedure()

    app._publish_attach_stage_audit = _audit_with_operator_abort  # type: ignore

    action = _action()
    app._qiki_pending_action = dict(action)
    app._seal_pending_decision(action)
    asyncio.run(app._execute_qiki_pending_action())
    proc = app._attach_procedure
    # добить возможные тики (если процедура пережила abort — она пойдёт дальше)
    for _ in range(6):
        app._attach_procedure_on_snapshot()
    asyncio.run(asyncio.sleep(0))

    assert proc.status == STATUS_ABORTED  # прерывание НЕ перезаписано
    body = get_body_structure_interactive_controller().snapshot().body
    assert len(body.modules) == 0  # тело не тронуто после «прервано»


# ── Фикс 2: TOCTOU пломбы — мутация вложенных параметров после authorize ────

def test_seal_freezes_nested_parameters_deep() -> None:
    params = {"module_id": "m1", "mount": "F09", "provided_capabilities": ["a"]}
    intent = CommandIntent(kind="BODY_ATTACH", subject="orionv.body", name="attach.module",
                           parameters=params, operator_facing_title="t")
    decision = seal_decision(decision_id="d1", intent=intent)
    params["provided_capabilities"].append("EVIL_CAP")  # мутация исходника после seal
    assert "EVIL_CAP" not in decision.intent.parameters["provided_capabilities"]


def test_bridge_recomputes_digest_before_effect() -> None:
    """Дрейф пломбы между authorize и effect → тело НЕ трогается."""
    params = {"module_id": "m1", "mount": "F09", "provided_capabilities": ["a"]}
    intent = CommandIntent(kind="BODY_ATTACH", subject="orionv.body", name="attach.module",
                           parameters=params, operator_facing_title="t")
    decision = seal_decision(decision_id="d2", intent=intent)
    auth = authorize_publish(decision, candidate_kind="BODY_ATTACH",
                             candidate_subject="orionv.body", candidate_name="attach.module",
                             candidate_parameters=dict(params))
    assert auth.allowed and auth.decision.status is DecisionStatus.PUBLISHED
    # злонамеренная мутация ПОСЛЕ authorize, ДО effect (through shared ref)
    auth.decision.intent.parameters["provided_capabilities"] = ["EVIL_CAP"]

    touched = {"n": 0}

    def _runner():
        touched["n"] += 1
        return True, "audit-1"

    result = bridge_decision_to_body(auth.decision, power_blocked=False,
                                     thermal_blocked=False, attach_runner=_runner)
    assert touched["n"] == 0  # тело НЕ тронуто
    assert result.reached_body is False
    assert any("SEAL" in c or "DRIFT" in c for c in result.reason_codes)


# ── Фикс 3: фоновые задачи держатся и логируют исключения ────────────────────

def test_spawn_task_keeps_reference_and_logs_exception(caplog) -> None:
    app = OrionVApp()

    async def _boom():
        raise RuntimeError("background boom")

    async def _main():
        task = app._spawn_task(_boom())
        assert task in app._bg_tasks  # ссылка держится (GC не убьёт)
        with caplog.at_level(logging.ERROR):
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        assert task not in app._bg_tasks  # по завершении — вычищена

    asyncio.run(_main())
    assert any("background boom" in r.getMessage() for r in caplog.records)  # не молча
