"""M7-M9 live-wiring: одобренное BODY_ATTACH-решение идёт к телу через мост.

ADR-0018: команда телу исполняется локальным body-конвейером (не шиной), под
полным M5/M6-гейтом и fail-closed предусловиями. Негативы (RED) первыми:
спуф и блок-предусловия НЕ достигают тела.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.shared.models.qiki_chat import (
    BilingualText,
    QikiChatResponseV1,
    QikiLegalityV1,
    QikiMode,
    QikiProposalV1,
    QikiProposedActionV1,
)


def _body_action() -> dict:
    return {
        "action_kind": "BODY_ATTACH",
        "proposal_id": "p-body-1",
        "title_ru": "Подтвердить установку модуля",
        "title_en": "Confirm module attach",
        "subject": "orionv.body",
        "name": "attach.module",
        "parameters": {
            "module_id": "test_sensor_module_001",
            "mount": "F06",
            "module_class": "sensor",
            "provided_capabilities": ["basic_sensor_read"],
            "quantity": 2,
            "passport_damaged": False,
        },
        "dry_run": False,
    }


def _allowed_response() -> QikiChatResponseV1:
    return QikiChatResponseV1(
        request_id=uuid4(),
        ok=True,
        mode=QikiMode.FACTORY,
        legality=QikiLegalityV1(
            status="allowed",
            domain="physics",
            reason_code="BODY_ATTACH_READY",
            reason=BilingualText(en="ok", ru="ок"),
        ),
        proposals=[
            QikiProposalV1(
                proposal_id="p-body-1",
                title=BilingualText(en="t", ru="т"),
                justification=BilingualText(en="j", ru="о"),
                confidence=1.0,
                priority=85,
                proposed_actions=[
                    QikiProposedActionV1(
                        kind="BODY_ATTACH",
                        subject="orionv.body",
                        name="attach.module",
                        parameters={"module_id": "test_sensor_module_001", "mount": "F06"},
                        dry_run=False,
                    )
                ],
            )
        ],
    )


HEALTHY_SNAPSHOT = {
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


def _app(snapshot: dict | None) -> tuple[OrionVApp, dict]:
    calls = {"runner": 0, "audit": []}
    app = OrionVApp()
    app._qiki_last_response = _allowed_response()
    app._qiki_pending_action = _body_action()
    app._snapshot = dict(snapshot or {})
    app._set_help_text = lambda *a, **k: None  # type: ignore
    app._set_last_command_loop_state = lambda *a, **k: None  # type: ignore
    app._request_refresh_ui = lambda: None  # type: ignore

    def _stub_runner(params=None, *, decision_id="") -> tuple[bool, str]:
        calls["runner"] += 1
        return True, "audit-evt-1"

    app._attach_runner_from_params = _stub_runner  # type: ignore

    async def _capture_audit(subject: str, payload: dict) -> None:
        calls["audit"].append((subject, payload))

    app._publish_audit_event = _capture_audit  # type: ignore
    return app, calls


def _seal(app: OrionVApp, action: dict) -> None:
    app._seal_pending_decision(action)


def _drive_ticks(app: OrionVApp, n: int = 8) -> None:
    for _ in range(n):
        proc = app._attach_procedure
        if proc is None or proc.status != "running":
            return
        app._attach_procedure_on_snapshot()


def test_red_spoofed_body_attach_does_not_reach_body() -> None:
    """RED: подмена команды после пломбы -> тело НЕ тронуто (M5 в BODY-пути)."""
    app, calls = _app(HEALTHY_SNAPSHOT)
    _seal(app, _body_action())
    spoofed = _body_action()
    spoofed["parameters"] = {"module_id": "test_sensor_module_001", "mount": "F01"}
    app._qiki_pending_action = spoofed
    asyncio.run(app._execute_qiki_pending_action())
    assert calls["runner"] == 0, "спуф достиг тела"


def test_red_power_precondition_blocks_body() -> None:
    """RED: load_shedding -> deferred, конвейер не вызван, отказ не немой."""
    snapshot = {
        "power": {**HEALTHY_SNAPSHOT["power"], "load_shedding": True},
        "thermal": HEALTHY_SNAPSHOT["thermal"],
    }
    app, calls = _app(snapshot)
    _seal(app, _body_action())
    asyncio.run(app._execute_qiki_pending_action())
    _drive_ticks(app)  # P2: окно ловится на тике переноса
    assert calls["runner"] == 0, "power block не остановил тело"
    # ADR-0020: окно закрыто -> процедура holding, отказ не немой (стадийный аудит)
    assert app._attach_procedure is not None and app._attach_procedure.status == "holding"
    stage_events = [p for _, p in calls["audit"] if p.get("kind_event") == "qiki_attach_stage"]
    # P2: окно ловится на тике переноса кодом источника (до моста не доходит)
    assert any("load_shedding" in (e.get("reason_codes") or []) for e in stage_events)


def test_red_missing_power_telemetry_fail_closed() -> None:
    """RED: нет power-телеметрии -> fail-closed deferred (предусловия недоступны)."""
    app, calls = _app({})
    _seal(app, _body_action())
    asyncio.run(app._execute_qiki_pending_action())
    _drive_ticks(app)
    assert calls["runner"] == 0, "отсутствие телеметрии не заблокировало тело"
    assert app._attach_procedure is not None and app._attach_procedure.status == "holding"
    stage_events = [p for _, p in calls["audit"] if p.get("kind_event") == "qiki_attach_stage"]
    assert any("POWER_TELEM_MISSING" in (e.get("reason_codes") or []) for e in stage_events)


def test_green_approved_attach_reaches_body_with_audit() -> None:
    """GREEN: allowed+seal+authorize+чистые предусловия -> тело, effect ok, аудит."""
    app, calls = _app(HEALTHY_SNAPSHOT)
    _seal(app, _body_action())
    asyncio.run(app._execute_qiki_pending_action())
    _drive_ticks(app)
    assert calls["runner"] == 1
    assert app._qiki_last_response.consequence.status == "confirmed"
    decision_traces = [p for _, p in calls["audit"] if p.get("kind_event") == "qiki_body_attach_decision"]
    assert decision_traces, "нет трассы решения в аудите"
    payload = decision_traces[0]
    assert payload["runtime_claim_status"] == "runtime_effect_confirmed"
    assert payload["stages"]["effect"] == "ok"
    assert payload["stages"]["audit"] == "ok"


def test_green_live_runner_uses_real_body_pipeline() -> None:
    """GREEN: runner зовёт живой конвейер, параметры — ТОЛЬКО из пломбы (P3)."""
    from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
        get_body_structure_interactive_controller,
        reset_body_structure_interactive_state,
    )
    from qiki.shared.command_decision import authorize_publish

    reset_body_structure_interactive_state()
    try:
        app = OrionVApp()
        app._set_help_text = lambda *a, **k: None  # type: ignore
        # без пломбы тело не трогается
        assert app._body_attach_runner() == (False, "")

        app._seal_pending_decision(_body_action())
        sealed = app._decision_store.get(app._pending_decision_id)
        kind, subject, name, params = sealed.sealed_command
        app._decision_store.put(
            authorize_publish(
                sealed, candidate_kind=kind, candidate_subject=subject,
                candidate_name=name, candidate_parameters=params,
            ).decision
        )
        attached, audit_event_id = app._body_attach_runner()
        assert attached is True and audit_event_id
        body = get_body_structure_interactive_controller().snapshot().body
        assert [str(m.get("module_id")) for m in body.modules] == ["test_sensor_module_001"]
    finally:
        reset_body_structure_interactive_state()


def test_policy_attach_intent_contract() -> None:
    """Policy: «установи модуль» -> BODY_ATTACH-кандидат, параметры = константы тела."""
    from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
        BODY_STRUCTURE_TEST_MODULE_ID,
        BODY_STRUCTURE_TEST_MOUNT,
    )
    from qiki.services.q_core_agent.qiki_orion_intents_service import (
        _build_attach_module_response,
        _is_attach_module_command,
    )
    from qiki.shared.models.qiki_chat import QikiChatInput, QikiChatRequestV1

    assert _is_attach_module_command("q: установи модуль")
    assert _is_attach_module_command("Установить модуль на гнездо")
    assert not _is_attach_module_command("доложи состояние")

    req = QikiChatRequestV1(
        request_id=uuid4(),
        ts_epoch_ms=0,
        input=QikiChatInput(text="установи модуль"),
    )
    resp = _build_attach_module_response(req=req, mode=QikiMode.FACTORY)
    assert resp.legality.status == "allowed"
    action = resp.proposals[0].proposed_actions[0]
    assert action.kind == "BODY_ATTACH"
    assert action.subject == "orionv.body"
    assert action.name == "attach.module"
    assert action.parameters["module_id"] == BODY_STRUCTURE_TEST_MODULE_ID
    assert action.parameters["mount"] == BODY_STRUCTURE_TEST_MOUNT
