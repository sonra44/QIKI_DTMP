"""Мост «одобренное решение → тело» (M7-M9, F5 design §6).

Связывает ПРОВЕДЁННЫЙ CommandDecision (M5/M6) с уже готовым конвейером тела
(run_attach_pipeline, слайсы 0001-0008) — НОВОГО body-кода не пишем. Конвейер
инъектируется как runner, поэтому модуль остаётся чистым и тестируемым.

Предусловия питания/тепла берутся из готовых view-model'ей (caller передаёт
готовые флаги блокировки — новой power/thermal-логики тут нет). Если предусловие
не выполнено — эффект НЕ инициируется (deferred), тело не трогается.

JSONL-трасса: полный жизненный цикл решения одной строкой на запись — для
реплея и экспорта.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from qiki.shared.command_decision import (
    CommandDecision,
    DecisionStatus,
    StageState,
    mark_stage,
)

# Reason codes предусловий.
PRECOND_POWER_BLOCK = "BRIDGE_POWER_BLOCK"
PRECOND_THERMAL_BLOCK = "BRIDGE_THERMAL_BLOCK"
PRECOND_NOT_PUBLISHED = "BRIDGE_DECISION_NOT_PUBLISHED"
# ADR-0020 P0: мост однократен — исполненное решение к телу не возвращается.
DECISION_ALREADY_EXECUTED = "DECISION_ALREADY_EXECUTED"


def preconditions_ok(*, power_blocked: bool, thermal_blocked: bool) -> tuple[bool, tuple[str, ...]]:
    """Проверка предусловий тела. Флаги — из готовых power/thermal view-model'ей."""
    codes: list[str] = []
    if power_blocked:
        codes.append(PRECOND_POWER_BLOCK)
    if thermal_blocked:
        codes.append(PRECOND_THERMAL_BLOCK)
    return (not codes, tuple(codes))


# runner возвращает (attached: bool, audit_event_id: str) — тонкая обёртка над
# существующим run_attach_pipeline, инъектируется вызывающим кодом.
AttachRunner = Callable[[], "tuple[bool, str]"]


@dataclass(frozen=True)
class BridgeResult:
    decision: CommandDecision
    reached_body: bool
    reason_codes: tuple[str, ...]


def bridge_decision_to_body(
    decision: CommandDecision,
    *,
    power_blocked: bool,
    thermal_blocked: bool,
    attach_runner: AttachRunner,
) -> BridgeResult:
    """Провести решение к телу через готовый конвейер.

    Правила:
    - только PUBLISHED-решение допускается к телу (иначе — отказ, тело не тронуто);
    - предусловия питания/тепла блокируют эффект (deferred), тело не тронуто;
    - при успехе: ack=ok, effect по результату конвейера, audit=ok при audit_event_id.
    """
    if decision.status is not DecisionStatus.PUBLISHED:
        return BridgeResult(decision=decision, reached_body=False, reason_codes=(PRECOND_NOT_PUBLISHED,))

    # ADR-0020 P0: однократность — решение с тронутыми поздними ступенями
    # уже жило у тела (или было принято), повторный заход запрещён.
    if decision.stages.ack is not StageState.NONE or decision.stages.effect is not StageState.NONE:
        return BridgeResult(decision=decision, reached_body=False, reason_codes=(DECISION_ALREADY_EXECUTED,))

    ok, codes = preconditions_ok(power_blocked=power_blocked, thermal_blocked=thermal_blocked)
    if not ok:
        # Предусловие не выполнено — эффект не инициируется, тело не трогается.
        # ADR-0020 P0: ack НЕ ставится — deferred не является принятием конвейером.
        return BridgeResult(decision=decision, reached_body=False, reason_codes=codes)

    attached, audit_event_id = attach_runner()
    updated = mark_stage(
        decision,
        ack=StageState.OK,
        effect=StageState.OK if attached else StageState.FAILED,
        audit=StageState.OK if audit_event_id else StageState.FAILED,
    )
    return BridgeResult(decision=updated, reached_body=True, reason_codes=())


def decision_trace_record(decision: CommandDecision, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Одна запись трассы жизненного цикла решения (для JSONL/реплея)."""
    record: dict[str, Any] = {
        "decision_id": decision.decision_id,
        "status": decision.status.value,
        "kind": decision.intent.kind,
        "subject": decision.intent.subject,
        "name": decision.intent.name,
        "operator_facing_title": decision.intent.operator_facing_title,
        "digest": decision.digest,
        "stages": {
            "validation": decision.stages.validation.value,
            "publish": decision.stages.publish.value,
            "ack": decision.stages.ack.value,
            "effect": decision.stages.effect.value,
            "audit": decision.stages.audit.value,
        },
        "reason_codes": list(decision.reason_codes),
    }
    if extra:
        record.update(extra)
    return record


def decision_trace_jsonl(records: Sequence[dict[str, Any]]) -> str:
    """Сериализовать записи трассы в JSONL (одна запись на строку)."""
    return "\n".join(json.dumps(rec, ensure_ascii=False, sort_keys=True) for rec in records)
