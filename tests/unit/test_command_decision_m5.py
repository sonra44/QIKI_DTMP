"""M5: CommandDecision — RED-тест спуфинга ПЕРВЫМ (закрытие Д3), затем контракт.

Д3 (F5 design §2.2): оператор подтверждает title, исполняется provider-controlled
subject/name/params — их можно рассинхронить. CommandDecision пломбирует точную
команду при одобрении; публикация разрешена только при совпадении с пломбой.
"""

from __future__ import annotations

from qiki.shared.command_decision import (
    CMD_ALREADY_PUBLISHED,
    CMD_EMPTY_COMMAND,
    CMD_SPOOF_MISMATCH,
    CommandIntent,
    DecisionStatus,
    DecisionStore,
    StageState,
    authorize_publish,
    mark_stage,
    seal_decision,
)


def _benign_intent() -> CommandIntent:
    return CommandIntent(
        kind="NATS_COMMAND",
        subject="qiki.commands.control",
        name="safe_pause_resume",
        parameters={"target": "ALLY-4D1ED5"},
        operator_facing_title="Возобновить наблюдение безопасно",
    )


# ─────────────────────────── RED: спуфинг ───────────────────────────

def test_RED_spoofed_name_after_approval_is_not_published():
    """Одобрен безобидный, публикуется подменённый name → ОТКАЗ (ядро Д3)."""
    decision = seal_decision(decision_id="d-1", intent=_benign_intent())
    assert decision.status is DecisionStatus.SEALED

    # Провайдер подменил action.name после одобрения (benign title остался прежним).
    auth = authorize_publish(
        decision,
        candidate_kind="NATS_COMMAND",
        candidate_subject="qiki.commands.control",
        candidate_name="sim.rcs.fire",  # РАСХОЖДЕНИЕ с запломбированным
        candidate_parameters={"target": "ALLY-4D1ED5"},
    )
    assert auth.allowed is False
    assert CMD_SPOOF_MISMATCH in auth.reason_codes
    assert auth.decision.status is DecisionStatus.REJECTED
    assert auth.decision.stages.publish is StageState.FAILED


def test_RED_spoofed_parameters_rejected():
    decision = seal_decision(decision_id="d-2", intent=_benign_intent())
    auth = authorize_publish(
        decision,
        candidate_kind="NATS_COMMAND",
        candidate_subject="qiki.commands.control",
        candidate_name="safe_pause_resume",
        candidate_parameters={"target": "HOSTILE-9"},  # подменён параметр
    )
    assert auth.allowed is False and CMD_SPOOF_MISMATCH in auth.reason_codes


def test_RED_spoofed_subject_rejected():
    decision = seal_decision(decision_id="d-3", intent=_benign_intent())
    auth = authorize_publish(
        decision,
        candidate_kind="NATS_COMMAND",
        candidate_subject="qiki.commands.weapons",  # другой subject
        candidate_name="safe_pause_resume",
        candidate_parameters={"target": "ALLY-4D1ED5"},
    )
    assert auth.allowed is False and CMD_SPOOF_MISMATCH in auth.reason_codes


# ─────────────────────────── GREEN: честный путь ───────────────────────────

def test_matching_command_is_authorized():
    decision = seal_decision(decision_id="d-4", intent=_benign_intent())
    kind, subject, name, params = decision.sealed_command
    auth = authorize_publish(
        decision, candidate_kind=kind, candidate_subject=subject, candidate_name=name, candidate_parameters=params
    )
    assert auth.allowed is True
    assert auth.decision.status is DecisionStatus.PUBLISHED
    assert auth.decision.stages.publish is StageState.OK


def test_idempotent_double_publish_rejected():
    decision = seal_decision(decision_id="d-5", intent=_benign_intent())
    kind, subject, name, params = decision.sealed_command
    first = authorize_publish(
        decision, candidate_kind=kind, candidate_subject=subject, candidate_name=name, candidate_parameters=params
    )
    assert first.allowed is True
    # Повторная публикация того же решения — отказ (защита от повторов).
    second = authorize_publish(
        first.decision, candidate_kind=kind, candidate_subject=subject, candidate_name=name, candidate_parameters=params
    )
    assert second.allowed is False and CMD_ALREADY_PUBLISHED in second.reason_codes


def test_empty_command_sealed_as_rejected():
    intent = CommandIntent(kind="NATS_COMMAND", subject="", name="", parameters={}, operator_facing_title="пусто")
    decision = seal_decision(decision_id="d-6", intent=intent)
    assert decision.status is DecisionStatus.REJECTED
    assert CMD_EMPTY_COMMAND in decision.reason_codes
    auth = authorize_publish(
        decision, candidate_kind="NATS_COMMAND", candidate_subject="", candidate_name="", candidate_parameters={}
    )
    assert auth.allowed is False


def test_stages_are_separate_not_collapsed():
    decision = seal_decision(decision_id="d-7", intent=_benign_intent())
    kind, subject, name, params = decision.sealed_command
    published = authorize_publish(
        decision, candidate_kind=kind, candidate_subject=subject, candidate_name=name, candidate_parameters=params
    ).decision
    # ack/effect/audit ещё не наступили — не схлопнуты в publish.
    assert published.stages.ack is StageState.NONE
    assert published.stages.effect is StageState.NONE
    updated = mark_stage(published, ack=StageState.OK)
    assert updated.stages.ack is StageState.OK
    assert updated.stages.effect is StageState.NONE  # раздельно


def test_param_key_order_does_not_break_binding():
    """Пломба стабильна к порядку ключей (каноничный digest)."""
    intent = CommandIntent(
        kind="NATS_COMMAND",
        subject="qiki.commands.control", name="cmd",
        parameters={"a": 1, "b": 2}, operator_facing_title="t",
    )
    decision = seal_decision(decision_id="d-8", intent=intent)
    auth = authorize_publish(
        decision, candidate_kind="NATS_COMMAND", candidate_subject="qiki.commands.control", candidate_name="cmd",
        candidate_parameters={"b": 2, "a": 1},  # другой порядок — та же команда
    )
    assert auth.allowed is True


def test_decision_store_idempotency():
    store = DecisionStore()
    d = seal_decision(decision_id="d-9", intent=_benign_intent())
    store.put(d)
    assert store.has("d-9") and store.get("d-9").decision_id == "d-9"
    assert store.get("absent") is None
