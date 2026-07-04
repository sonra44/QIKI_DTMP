"""Конверт QIKI-диалога v2 (M4, F5 design §4; словари — ADR-0017).

v2 = v1 + auth_context/evidence_context/command_intent_class/client_claim_level
(запрос) и decision_preview/evidence (ответ).

Правило совместимости: сервис отвечает В ВЕРСИИ ЗАПРОСА (v2 только на v2),
поэтому v1-клиенты не видят незнакомых полей (extra="forbid" у v1 — осознанно).
Флаг включения v2 живёт на КЛИЕНТЕ (консоль: ORION_QIKI_ENVELOPE_V2=1).

Секрет-гигиена: auth_context.token_id — отпечаток токена, НИКОГДА не сам токен.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import Field

from qiki.shared.models.qiki_chat import (
    QikiChatRequestV1,
    QikiChatResponseV1,
    _StrictModel,
)


class RuntimeClaimStatus(str, Enum):
    """ADR-0017: статус утверждения о runtime, которое несёт ответ.

    Ступени validation/publish/ack/effect живут в CommandDecision (M5),
    здесь их схлопывать нельзя (ADR-0015).
    """

    LOCAL_UI_LOOP_NO_RUNTIME_COMMAND = "local_ui_loop_no_runtime_command"
    CANDIDATE_ONLY = "candidate_only"
    RUNTIME_COMMAND_PENDING = "runtime_command_pending"
    RUNTIME_EFFECT_UNCONFIRMED = "runtime_effect_unconfirmed"
    RUNTIME_EFFECT_CONFIRMED = "runtime_effect_confirmed"


class EvidenceSourceType(str, Enum):
    """ADR-0017: словарь evidence_claim + provider (LLM через gateway)."""

    TELEMETRY = "telemetry"
    DERIVED = "derived"
    CALCULATION = "calculation"
    TARGET_ONLY = "target-only"
    EVENT = "event"
    COMMAND = "command"
    PROVIDER = "provider"


# Канонический словарь доверия §15.5 (+ принятый консолью fixture_only).
# ADR-0017 его НЕ расширяет; менять — только новым ADR + RAG-gate.
TrustStatus = Literal[
    "trusted",
    "degraded",
    "conflicting",
    "blind",
    "stale",
    "missing",
    "local_reconstruction",
    "hypothesis",
    "fixture_only",
]


class AuthContext(_StrictModel):
    """Кто спрашивает: логический субъект, сессия, права, отпечаток токена."""

    subject: str
    session: str
    scopes: list[str] = Field(default_factory=list)
    token_id: str = "none"  # отпечаток (fingerprint), не секрет


class EvidenceContext(_StrictModel):
    """Что клиент знает о доверии контекста, из которого задан вопрос."""

    sensor_trust: TrustStatus = "missing"
    source: str = ""
    runtime_claim_status: RuntimeClaimStatus = RuntimeClaimStatus.LOCAL_UI_LOOP_NO_RUNTIME_COMMAND


class DecisionPreview(_StrictModel):
    """Предпросмотр пути решения (read-only; сами ступени — в CommandDecision)."""

    validation_layers: list[str] = Field(default_factory=list)
    next_step: str = ""


class ResponseEvidence(_StrictModel):
    """§19.4-совместимая пометка происхождения ответа."""

    source_type: EvidenceSourceType
    source_id: str
    trust_status: TrustStatus
    freshness: Literal["fresh", "stale", "unknown"] = "unknown"
    runtime_claim_status: RuntimeClaimStatus


class QikiChatRequestV2(QikiChatRequestV1):
    version: Literal[2] = 2  # type: ignore[assignment]
    auth_context: Optional[AuthContext] = None
    evidence_context: Optional[EvidenceContext] = None
    command_intent_class: str = "unknown"  # словарь классов — предмет отдельного ADR
    client_claim_level: str = "none"


class QikiChatResponseV2(QikiChatResponseV1):
    version: Literal[2] = 2  # type: ignore[assignment]
    decision_preview: Optional[DecisionPreview] = None
    evidence: Optional[ResponseEvidence] = None


def parse_chat_request(payload: dict[str, Any]) -> QikiChatRequestV1 | QikiChatRequestV2:
    """Диспатч по version: v2 при version=2, иначе v1 (по умолчанию)."""
    if payload.get("version") == 2:
        return QikiChatRequestV2.model_validate(payload)
    return QikiChatRequestV1.model_validate(payload)


def parse_chat_response(payload: dict[str, Any]) -> QikiChatResponseV1 | QikiChatResponseV2:
    """Диспатч ответа по version (консольный приёмник)."""
    if payload.get("version") == 2:
        return QikiChatResponseV2.model_validate(payload)
    return QikiChatResponseV1.model_validate(payload)


def upgrade_response_to_v2(
    response: QikiChatResponseV1,
    *,
    evidence: ResponseEvidence,
    decision_preview: Optional[DecisionPreview] = None,
) -> QikiChatResponseV2:
    """Поднять готовый v1-ответ до v2, добавив evidence/preview.

    request_id и всё содержимое v1 сохраняются как есть (сквозной request_id —
    gate M4).
    """
    payload = response.model_dump(mode="python")
    payload["version"] = 2
    return QikiChatResponseV2.model_validate(
        {
            **payload,
            "decision_preview": decision_preview.model_dump(mode="python") if decision_preview else None,
            "evidence": evidence.model_dump(mode="python"),
        }
    )
