"""P3 (ADR-0020 §6): строка УСТАНОВКА в зоне РЕШЕНИЕ + условие допустимости + лента.

show-when: строка живёт только при активной процедуре; hold несёт «условие,
при котором действие станет допустимым» (долг G1); записи стадий — говорящий
«ПРОЦЕДУРА», не голос QIKI.
"""

from __future__ import annotations

import asyncio

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    reset_body_structure_interactive_state,
)
from qiki.services.operator_console.orion_v.screens.qiki_dialog import merge_dialog_lines

HEALTHY = {
    "power": {"soc_pct": 80, "supercap_soc_pct": 90, "bus_v": 28.0, "bus_a": 3.0,
              "load_shedding": False, "pdu_throttled": False},
    "thermal": {"nodes": [
        {"id": "T_core", "temp_c": 25.0, "warned": False, "tripped": False},
    ]},
    "sim_state": {"paused": False, "fsm_state": "RUNNING"},
}


def _action(mount="F09", *, damaged=False) -> dict:
    return {
        "action_kind": "BODY_ATTACH",
        "title_ru": "Установка",
        "subject": "orionv.body",
        "name": "attach.module",
        "parameters": {
            "module_id": "salvage_sensor_damaged_001" if damaged else "test_sensor_module_001",
            "mount": mount,
            "module_class": "sensor",
            "provided_capabilities": [],
            "quantity": 2,
            "passport_damaged": damaged,
        },
        "dry_run": False,
    }


def _app() -> OrionVApp:
    app = OrionVApp()
    app._snapshot = {k: (dict(v) if isinstance(v, dict) else v) for k, v in HEALTHY.items()}
    app._set_help_text = lambda *a, **k: None  # type: ignore
    app._set_last_command_loop_state = lambda *a, **k: None  # type: ignore
    app._request_refresh_ui = lambda: None  # type: ignore

    async def _audit(subject: str, payload: dict) -> None:
        return None

    app._publish_audit_event = _audit  # type: ignore
    return app


def _start(app: OrionVApp, action: dict) -> None:
    app._qiki_pending_action = dict(action)
    app._seal_pending_decision(action)
    asyncio.run(app._execute_qiki_pending_action())


def setup_function() -> None:
    reset_body_structure_interactive_state()


def teardown_function() -> None:
    reset_body_structure_interactive_state()


def test_show_when_no_procedure_no_line() -> None:
    app = _app()
    assert app._build_attach_procedure_lines() == []
    assert app._build_qiki_decision_preview_lines() == []


def test_transfer_line_shows_progress_and_controls() -> None:
    app = _app()
    _start(app, _action(mount="F09"))
    app._attach_procedure_on_snapshot()  # 1-й тик
    lines = app._build_attach_procedure_lines()
    assert lines and lines[0].startswith("УСТАНОВКА: S3 ПЕРЕНОС (1/4)")
    assert "q hold" in lines[0] and "q abort" in lines[0]
    # строка живёт в предпросмотре решения даже без кандидата
    assert app._build_qiki_decision_preview_lines()[0] == lines[0]


def test_hold_line_carries_admissibility_condition_power() -> None:
    app = _app()
    _start(app, _action(mount="F09"))
    app._snapshot["power"] = {**HEALTHY["power"], "load_shedding": True}
    app._attach_procedure_on_snapshot()  # оконная развилка
    lines = app._build_attach_procedure_lines()
    assert "HOLD" in lines[0] and "load_shedding" in lines[0]
    assert any("условие: PWR без load_shedding" in line for line in lines)


def test_hold_line_thermal_condition_with_trend() -> None:
    app = _app()
    _start(app, _action(mount="F09"))
    # два снапшота с горячим узлом — история для тренда
    for temp in (86.0, 84.5):
        app._snapshot["thermal"] = {
            "nodes": [{"id": "T_pdu", "temp_c": temp, "warned": True, "tripped": False}]
        }
        app._attach_procedure_on_snapshot()
    lines = app._build_attach_procedure_lines()
    condition = "\n".join(lines)
    assert "условие: THRM green" in condition
    assert "T_pdu 84.5°" in condition
    assert "тренд -1.5°/тик" in condition  # живой тренд, не выдумка


def test_damaged_fork_line() -> None:
    app = _app()
    _start(app, _action(damaged=True))
    lines = app._build_attach_procedure_lines()
    assert "РАЗВИЛКА [PASSPORT_DAMAGED]" in lines[0]
    assert any("исход решит конвейер" in line for line in lines)


def test_procedure_lines_speaker_is_not_qiki() -> None:
    app = _app()
    _start(app, _action(mount="F09"))
    assert app._attach_procedure_ledger, "стадии не попали в леджер процедуры"
    merged = merge_dialog_lines(
        operator_lines=(),
        voice_entries=(),
        procedure_lines=tuple(app._attach_procedure_ledger),
    )
    assert merged and all(line.speaker == "ПРОЦЕДУРА" for line in merged)
    assert any("S1 осмотр" in line.text for line in merged)
