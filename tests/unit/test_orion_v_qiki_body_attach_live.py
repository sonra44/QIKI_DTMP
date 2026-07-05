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
        "parameters": {"module_id": "test_sensor_module_001", "mount": "F06"},
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

    def _stub_runner() -> tuple[bool, str]:
        calls["runner"] += 1
        return True, "audit-evt-1"

    app._body_attach_runner = _stub_runner  # type: ignore

    async def _capture_audit(subject: str, payload: dict) -> None:
        calls["audit"].append((subject, payload))

    app._publish_audit_event = _capture_audit  # type: ignore
    return app, calls


def _seal(app: OrionVApp, action: dict) -> None:
    app._seal_pending_decision(action)


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
    assert calls["runner"] == 0, "power block не остановил тело"
    assert app._qiki_last_response.consequence.status == "not_sent"
    # немой отказ недопустим (канон §6): трасса ушла в аудит с причинами
    assert calls["audit"], "нет аудит-события"
    payload = calls["audit"][0][1]
    assert "BRIDGE_POWER_BLOCK" in payload["bridge_reason_codes"]


def test_red_missing_power_telemetry_fail_closed() -> None:
    """RED: нет power-телеметрии -> fail-closed deferred (предусловия недоступны)."""
    app, calls = _app({})
    _seal(app, _body_action())
    asyncio.run(app._execute_qiki_pending_action())
    assert calls["runner"] == 0, "отсутствие телеметрии не заблокировало тело"
    payload = calls["audit"][0][1]
    assert "POWER_TELEM_MISSING" in payload["precondition_detail"]


def test_green_approved_attach_reaches_body_with_audit() -> None:
    """GREEN: allowed+seal+authorize+чистые предусловия -> тело, effect ok, аудит."""
    app, calls = _app(HEALTHY_SNAPSHOT)
    _seal(app, _body_action())
    asyncio.run(app._execute_qiki_pending_action())
    assert calls["runner"] == 1
    assert app._qiki_last_response.consequence.status == "confirmed"
    subject, payload = calls["audit"][0]
    assert payload["runtime_claim_status"] == "runtime_effect_confirmed"
    assert payload["stages"]["effect"] == "ok"
    assert payload["stages"]["audit"] == "ok"


def test_green_live_runner_uses_real_body_pipeline() -> None:
    """GREEN: настоящий runner зовёт живой конвейер (тот же, что клавиша B)."""
    from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
        reset_body_structure_interactive_state,
    )

    reset_body_structure_interactive_state()
    try:
        app = OrionVApp()
        attached, audit_event_id = app._body_attach_runner()
        assert attached is True
        assert audit_event_id
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
