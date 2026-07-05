"""P0 (ADR-0020 §4): мост честен по ступеням и однократен.

RED первым: (1) deferred НЕ ставит ack=ok (сегодня ставит — ложь ступени
«конвейер принял»); (2) мост вызывается один раз за жизнь решения —
повторный вызов отклоняется DECISION_ALREADY_EXECUTED, тело не тронуто.
"""

from __future__ import annotations

from qiki.shared.command_decision import CommandIntent, StageState, authorize_publish, seal_decision
from qiki.shared.decision_body_bridge import (
    DECISION_ALREADY_EXECUTED,
    bridge_decision_to_body,
)


def _published(decision_id: str = "p0-1"):
    intent = CommandIntent(
        kind="BODY_ATTACH", subject="orionv.body", name="attach.module",
        parameters={"module_id": "m", "mount": "F06"}, operator_facing_title="t",
    )
    sealed = seal_decision(decision_id=decision_id, intent=intent)
    kind, subject, name, params = sealed.sealed_command
    return authorize_publish(
        sealed, candidate_kind=kind, candidate_subject=subject,
        candidate_name=name, candidate_parameters=params,
    ).decision


def test_red_deferred_keeps_ack_none() -> None:
    """Deferred = конвейер НЕ принимал запрос: ack обязан остаться none."""
    result = bridge_decision_to_body(
        _published(), power_blocked=True, thermal_blocked=False,
        attach_runner=lambda: (True, "x"),
    )
    assert result.reached_body is False
    assert result.decision.stages.ack is StageState.NONE, result.decision.stages
    assert result.decision.stages.effect is StageState.NONE


def test_red_bridge_is_single_shot_per_decision() -> None:
    """Второй вызов моста на исполненном решении — отказ, тело не тронуто."""
    calls = {"n": 0}

    def runner():
        calls["n"] += 1
        return True, "audit-1"

    first = bridge_decision_to_body(
        _published("p0-2"), power_blocked=False, thermal_blocked=False, attach_runner=runner,
    )
    assert first.reached_body is True and calls["n"] == 1

    second = bridge_decision_to_body(
        first.decision, power_blocked=False, thermal_blocked=False, attach_runner=runner,
    )
    assert second.reached_body is False
    assert DECISION_ALREADY_EXECUTED in second.reason_codes
    assert calls["n"] == 1  # конвейер не вызван повторно


def test_deferred_then_retry_is_allowed() -> None:
    """Deferred НЕ исполняет решение — повторный заход после окна легален."""
    calls = {"n": 0}

    def runner():
        calls["n"] += 1
        return True, "audit-2"

    deferred = bridge_decision_to_body(
        _published("p0-3"), power_blocked=True, thermal_blocked=False, attach_runner=runner,
    )
    assert deferred.reached_body is False and calls["n"] == 0

    retry = bridge_decision_to_body(
        deferred.decision, power_blocked=False, thermal_blocked=False, attach_runner=runner,
    )
    assert retry.reached_body is True and calls["n"] == 1
    assert retry.decision.stages.effect is StageState.OK
