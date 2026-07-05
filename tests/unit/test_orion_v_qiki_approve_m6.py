"""M6: q approve — блокирующий гейт одобрения.

Gate (F5 design §6): candidate-only/deferred/blocked не достигают шины;
approve идемпотентен. Одобрить можно только allowed-ответ.
"""

from __future__ import annotations

from uuid import uuid4

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.shared.command_decision import DecisionStatus
from qiki.shared.models.qiki_chat import (
    BilingualText,
    QikiChatResponseV1,
    QikiLegalityV1,
    QikiMode,
    QikiProposalV1,
    QikiProposedActionV1,
)


def _action() -> dict:
    return {
        "action_kind": "NATS_COMMAND",
        "proposal_id": "p-1",
        "title_ru": "Возобновить наблюдение безопасно",
        "title_en": "Resume safe observation",
        "subject": "qiki.commands.control",
        "name": "sim.dock.release",
        "parameters": {"target": "ALLY-1"},
        "dry_run": False,
    }


def _legality(status: str) -> QikiLegalityV1:
    return QikiLegalityV1(
        status=status,
        domain="protocol",
        reason_code=f"{status.upper()}_CODE",
        reason=BilingualText(en=status, ru=status),
    )


def _response(status: str) -> QikiChatResponseV1:
    return QikiChatResponseV1(
        request_id=uuid4(),
        ok=True,
        mode=QikiMode.FACTORY,
        legality=_legality(status),
        proposals=[
            QikiProposalV1(
                proposal_id="p-1",
                title=BilingualText(en="t", ru="т"),
                justification=BilingualText(en="j", ru="о"),
                confidence=1.0,
                priority=50,
                proposed_actions=[
                    QikiProposedActionV1(subject="qiki.commands.control", name="sim.dock.release", dry_run=False)
                ],
            )
        ],
    )


def _app_with(status: str) -> OrionVApp:
    app = OrionVApp()
    app._qiki_last_response = _response(status)
    app._qiki_pending_action = _action()
    app.push_screen = lambda *a, **k: (_ for _ in ()).throw(AssertionError("confirm dialog pushed"))  # type: ignore
    app._set_help_text = lambda *a, **k: None  # type: ignore
    app._set_last_command_loop_state = lambda *a, **k: None  # type: ignore
    app._request_refresh_ui = lambda: None  # type: ignore
    return app


def test_blocked_candidate_cannot_be_approved():
    app = _app_with("blocked")
    ok, reason = app._qiki_pending_is_approvable()
    assert ok is False and reason == "blocked"
    # Одобрение не пломбирует и не толкает подтверждение (push_screen бросил бы).
    app._confirm_qiki_pending_action()
    assert app._pending_decision_id is None


def test_deferred_candidate_cannot_be_approved():
    app = _app_with("deferred")
    ok, reason = app._qiki_pending_is_approvable()
    assert ok is False and reason == "deferred"
    app._confirm_qiki_pending_action()
    assert app._pending_decision_id is None


def test_candidate_only_no_legality_cannot_be_approved():
    app = OrionVApp()
    app._qiki_last_response = QikiChatResponseV1(request_id=uuid4(), ok=True, mode=QikiMode.FACTORY, legality=None)
    app._qiki_pending_action = _action()
    app.push_screen = lambda *a, **k: (_ for _ in ()).throw(AssertionError("confirm dialog pushed"))  # type: ignore
    app._set_help_text = lambda *a, **k: None  # type: ignore
    app._set_last_command_loop_state = lambda *a, **k: None  # type: ignore
    app._request_refresh_ui = lambda: None  # type: ignore
    ok, reason = app._qiki_pending_is_approvable()
    assert ok is False and reason == "candidate_only"


def test_allowed_candidate_seals_decision():
    pushed = {}
    app = _app_with("allowed")
    app.push_screen = lambda *a, **k: pushed.setdefault("yes", True)  # type: ignore
    app._confirm_qiki_pending_action()
    assert app._pending_decision_id is not None
    decision = app._decision_store.get(app._pending_decision_id)
    assert decision is not None and decision.status is DecisionStatus.SEALED
    assert pushed.get("yes") is True  # диалог подтверждения показан


def test_approve_idempotent_after_publish():
    app = _app_with("allowed")
    app.push_screen = lambda *a, **k: None  # type: ignore
    app._confirm_qiki_pending_action()
    decision_id = app._pending_decision_id
    assert decision_id is not None
    # Симулируем проведённое решение (published).
    from qiki.shared.command_decision import authorize_publish
    sealed = app._decision_store.get(decision_id)
    kind, subject, name, params = sealed.sealed_command
    published = authorize_publish(
        sealed, candidate_kind=kind, candidate_subject=subject, candidate_name=name, candidate_parameters=params
    ).decision
    app._decision_store.put(published)
    # Повторное одобрение — no-op: новый decision_id не создаётся.
    app._confirm_qiki_pending_action()
    assert app._pending_decision_id == decision_id


def test_pending_command_summary_formats_real_command_b1():
    """B1: summary команды человекочитаема, коды кодами."""
    app = OrionVApp()
    nats_cmd = app._pending_command_summary({
        "action_kind": "NATS_COMMAND", "subject": "qiki.commands.control",
        "name": "sim.dock.release", "parameters": {"target": "ALLY-1", "port": "A"},
    })
    assert "qiki.commands.control ▸ sim.dock.release" in nats_cmd
    assert "port=A" in nats_cmd and "target=ALLY-1" in nats_cmd
    proc = app._pending_command_summary({
        "action_kind": "ORION_PROCEDURE", "name": "safe_pause_resume", "parameters": {},
    })
    assert "процедура ▸ safe_pause_resume" in proc
    assert "параметры: —" in proc
