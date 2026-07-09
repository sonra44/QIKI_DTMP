"""CommandDecision v1 — связка одобренного намерения с ТОЧНОЙ командой (M5).

Закрывает Д3 (F5 design §2.2, §4): сегодня оператор подтверждает title, а
исполняется provider-controlled subject/name/parameters — их можно рассинхронить
(benign-заголовок + подменённый action.name). CommandDecision ПЛОМБИРУЕТ точную
команду в момент одобрения (binding_digest) и требует её совпадения при
публикации. Любое расхождение → отказ + аудит, команда НЕ исполняется.

Ступени раздельны (§18.4, ADR-0015, не схлопывать): validation / publish / ack /
effect / audit. Идемпотентность по decision_id: одна публикация на решение.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any


class StageState(str, Enum):
    NONE = "none"
    OK = "ok"
    FAILED = "failed"


class DecisionStatus(str, Enum):
    SEALED = "sealed"  # намерение одобрено и запломбировано, публикации ещё не было
    PUBLISHED = "published"  # ровно одна публикация состоялась
    REJECTED = "rejected"  # попытка публикации разошлась с пломбой — Д3-отказ


# Reason codes (§18.6 совместимо).
CMD_SPOOF_MISMATCH = "CMD_SPOOF_MISMATCH"
CMD_ALREADY_PUBLISHED = "CMD_ALREADY_PUBLISHED"
CMD_EMPTY_COMMAND = "CMD_EMPTY_COMMAND"


def _canonical(kind: str, subject: str, name: str, parameters: dict[str, Any]) -> str:
    """Каноничное представление команды для пломбы (стабильный порядок ключей).

    kind включён в пломбу: процедуру нельзя подменить одноимённой NATS-командой.
    """
    return json.dumps(
        {"kind": kind, "subject": subject, "name": name, "parameters": parameters},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def binding_digest(kind: str, subject: str, name: str, parameters: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(kind, subject, name, parameters).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CommandIntent:
    """Ровно та команда, которую оператор ОДОБРИЛ, вместе с показанным заголовком.

    kind разделяет пути исполнения: NATS_COMMAND (нужен subject) vs ORION_PROCEDURE
    (subject пуст, идентичность — по name). Пломба покрывает оба.
    """

    kind: str
    subject: str
    name: str
    parameters: dict[str, Any]
    operator_facing_title: str


@dataclass(frozen=True)
class DecisionStages:
    validation: StageState = StageState.NONE
    publish: StageState = StageState.NONE
    ack: StageState = StageState.NONE
    effect: StageState = StageState.NONE
    audit: StageState = StageState.NONE


@dataclass(frozen=True)
class CommandDecision:
    decision_id: str
    intent: CommandIntent
    digest: str
    status: DecisionStatus = DecisionStatus.SEALED
    stages: DecisionStages = field(default_factory=DecisionStages)
    reason_codes: tuple[str, ...] = ()

    @property
    def sealed_command(self) -> tuple[str, str, str, dict[str, Any]]:
        # deepcopy: вложенные структуры пломбы нельзя мутировать через возврат (TOCTOU).
        return (self.intent.kind, self.intent.subject, self.intent.name, copy.deepcopy(self.intent.parameters))


def seal_decision(*, decision_id: str, intent: CommandIntent) -> CommandDecision:
    """Запломбировать одобренное намерение. validation=ok, если есть name.

    subject обязателен только для NATS_COMMAND; у ORION_PROCEDURE он пуст
    легитимно (идентичность — по name). Пустой name — всегда невалидно.
    """
    # Пломба владеет СВОЕЙ глубокой копией параметров: мутация исходного dict
    # (в т.ч. вложенных списков/словарей) после seal не меняет одобренное (TOCTOU).
    intent = replace(intent, parameters=copy.deepcopy(intent.parameters))
    digest = binding_digest(intent.kind, intent.subject, intent.name, intent.parameters)
    subject_required = intent.kind.strip().upper() == "NATS_COMMAND"
    invalid = not intent.name.strip() or (subject_required and not intent.subject.strip())
    if invalid:
        return CommandDecision(
            decision_id=decision_id,
            intent=intent,
            digest=digest,
            status=DecisionStatus.REJECTED,
            stages=DecisionStages(validation=StageState.FAILED),
            reason_codes=(CMD_EMPTY_COMMAND,),
        )
    return CommandDecision(
        decision_id=decision_id,
        intent=intent,
        digest=digest,
        status=DecisionStatus.SEALED,
        stages=DecisionStages(validation=StageState.OK),
    )


@dataclass(frozen=True)
class PublishAuthorization:
    allowed: bool
    decision: CommandDecision
    reason_codes: tuple[str, ...] = ()


def authorize_publish(
    decision: CommandDecision,
    *,
    candidate_kind: str,
    candidate_subject: str,
    candidate_name: str,
    candidate_parameters: dict[str, Any],
) -> PublishAuthorization:
    """Разрешить публикацию ТОЛЬКО если кандидат-команда совпадает с пломбой.

    Это и есть закрытие Д3: то, что публикуется, обязано быть побитово тем, что
    оператор одобрил. Расхождение (подменённый name/subject/params) → отказ.
    Идемпотентность: повторная публикация одного decision_id → отказ.
    """
    if decision.status == DecisionStatus.PUBLISHED:
        return PublishAuthorization(allowed=False, decision=decision, reason_codes=(CMD_ALREADY_PUBLISHED,))
    if decision.status == DecisionStatus.REJECTED:
        return PublishAuthorization(allowed=False, decision=decision, reason_codes=decision.reason_codes)

    candidate_digest = binding_digest(candidate_kind, candidate_subject, candidate_name, candidate_parameters)
    if candidate_digest != decision.digest:
        rejected = replace(
            decision,
            status=DecisionStatus.REJECTED,
            stages=replace(decision.stages, publish=StageState.FAILED),
            reason_codes=decision.reason_codes + (CMD_SPOOF_MISMATCH,),
        )
        return PublishAuthorization(allowed=False, decision=rejected, reason_codes=(CMD_SPOOF_MISMATCH,))

    published = replace(
        decision,
        status=DecisionStatus.PUBLISHED,
        stages=replace(decision.stages, publish=StageState.OK),
    )
    return PublishAuthorization(allowed=True, decision=published)


def mark_stage(decision: CommandDecision, *, ack=None, effect=None, audit=None) -> CommandDecision:
    """Обновить поздние ступени (ack/effect/audit) после публикации. Раздельно."""
    return replace(
        decision,
        stages=replace(
            decision.stages,
            ack=ack or decision.stages.ack,
            effect=effect or decision.stages.effect,
            audit=audit or decision.stages.audit,
        ),
    )


class DecisionStore:
    """Реестр решений по decision_id. Идемпотентность и защита от повторов."""

    def __init__(self) -> None:
        self._by_id: dict[str, CommandDecision] = {}

    def put(self, decision: CommandDecision) -> None:
        self._by_id[decision.decision_id] = decision

    def get(self, decision_id: str) -> CommandDecision | None:
        return self._by_id.get(decision_id)

    def has(self, decision_id: str) -> bool:
        return decision_id in self._by_id
