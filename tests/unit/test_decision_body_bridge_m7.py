"""M7-M9: мост решение→тело — предусловия, делегирование конвейеру, JSONL-трасса."""

from __future__ import annotations

import json

from qiki.shared.command_decision import (
    CommandIntent,
    StageState,
    authorize_publish,
    seal_decision,
)
from qiki.shared.decision_body_bridge import (
    PRECOND_NOT_PUBLISHED,
    PRECOND_POWER_BLOCK,
    PRECOND_THERMAL_BLOCK,
    bridge_decision_to_body,
    decision_trace_jsonl,
    decision_trace_record,
    preconditions_ok,
)


def _published_decision() -> "object":
    intent = CommandIntent(
        kind="NATS_COMMAND",
        subject="qiki.commands.control",
        name="attach.module",
        parameters={"module_id": "m1"},
        operator_facing_title="Установить модуль m1",
    )
    sealed = seal_decision(decision_id="d-1", intent=intent)
    kind, subject, name, params = sealed.sealed_command
    return authorize_publish(
        sealed, candidate_kind=kind, candidate_subject=subject, candidate_name=name, candidate_parameters=params
    ).decision


def test_preconditions_ok_when_clear():
    ok, codes = preconditions_ok(power_blocked=False, thermal_blocked=False)
    assert ok is True and codes == ()


def test_preconditions_report_both_blocks():
    ok, codes = preconditions_ok(power_blocked=True, thermal_blocked=True)
    assert ok is False
    assert PRECOND_POWER_BLOCK in codes and PRECOND_THERMAL_BLOCK in codes


def test_unpublished_decision_never_reaches_body():
    intent = CommandIntent(
        kind="NATS_COMMAND", subject="s", name="n", parameters={}, operator_facing_title="t"
    )
    sealed = seal_decision(decision_id="d-x", intent=intent)  # SEALED, не PUBLISHED
    called = {"n": 0}

    def runner():
        called["n"] += 1
        return True, "audit-1"

    result = bridge_decision_to_body(sealed, power_blocked=False, thermal_blocked=False, attach_runner=runner)
    assert result.reached_body is False
    assert PRECOND_NOT_PUBLISHED in result.reason_codes
    assert called["n"] == 0  # конвейер не вызван


def test_power_block_defers_effect_body_untouched():
    decision = _published_decision()
    called = {"n": 0}

    def runner():
        called["n"] += 1
        return True, "audit-1"

    result = bridge_decision_to_body(decision, power_blocked=True, thermal_blocked=False, attach_runner=runner)
    assert result.reached_body is False
    assert PRECOND_POWER_BLOCK in result.reason_codes
    assert called["n"] == 0  # тело не тронуто
    assert result.decision.stages.effect is StageState.NONE  # эффект не инициирован


def test_successful_bridge_marks_effect_and_audit():
    decision = _published_decision()

    def runner():
        return True, "audit-42"

    result = bridge_decision_to_body(decision, power_blocked=False, thermal_blocked=False, attach_runner=runner)
    assert result.reached_body is True
    assert result.decision.stages.ack is StageState.OK
    assert result.decision.stages.effect is StageState.OK
    assert result.decision.stages.audit is StageState.OK


def test_rejected_attach_marks_effect_failed():
    decision = _published_decision()

    def runner():
        return False, "audit-43"  # конвейер отклонил attach

    result = bridge_decision_to_body(decision, power_blocked=False, thermal_blocked=False, attach_runner=runner)
    assert result.reached_body is True
    assert result.decision.stages.effect is StageState.FAILED
    assert result.decision.stages.audit is StageState.OK  # событие записано


def test_trace_record_and_jsonl_roundtrip():
    decision = _published_decision()
    rec = decision_trace_record(decision, extra={"note": "bridge"})
    assert rec["decision_id"] == "d-1"
    assert rec["stages"]["publish"] == "ok"
    assert rec["name"] == "attach.module"
    assert rec["note"] == "bridge"
    jsonl = decision_trace_jsonl([rec, rec])
    lines = jsonl.splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["digest"] == decision.digest
    # секрета/сырого ключа в трассе нет по построению (только команда+ступени)
    assert "sk-" not in jsonl
