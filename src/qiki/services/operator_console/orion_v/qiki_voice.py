"""Голос QIKI — лента реплик QIKI ▸ (DISPLAY_CANON №8в, гэп G-C).

Каждый QikiChatResponseV1 отображается одной репликой: время приёма + тип
(ACK/REJECT/INFO) + русский текст. Сырые коды LEGALITY/TRUST уходят в tooltip
рамки зоны (решение оператора 2026-07-04; страж честности: тип и timestamp
обязаны быть НА строке реплики).

Честность (ADR-0014): тип REJECT для любого не-allowed арбитража (blocked/
unsafe/deferred — команда не исполняется), текст только из ответа QIKI
(reply → legality.reason → error.message), без выдуманных формулировок.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from qiki.shared.models.qiki_chat import QikiChatResponseV1

QIKI_VOICE_VISIBLE_LIMIT = 3
_TEXT_MAX_CHARS = 120

QikiVoiceKind = Literal["ACK", "REJECT", "INFO"]


@dataclass(frozen=True)
class QikiVoiceEntry:
    received_at: str  # стенное время приёма, "HH:MM:SSZ" (UTC)
    kind: QikiVoiceKind
    text: str
    legality_code: str | None  # "blocked [zone] ZONE_DENY"
    trust_code: str | None  # "degraded conf=0.62"


def build_qiki_voice_entry(response: QikiChatResponseV1, *, received_at: str) -> QikiVoiceEntry:
    legality = response.legality
    if legality is not None and legality.status == "allowed":
        kind: QikiVoiceKind = "ACK"
    elif legality is not None:
        kind = "REJECT"
    else:
        kind = "INFO"

    text = ""
    if response.reply is not None:
        text = (response.reply.body.ru or response.reply.body.en or "").strip()
    if not text and legality is not None:
        text = (legality.reason.ru or legality.reason.en or "").strip()
    if not text and response.error is not None:
        text = (response.error.message.ru or response.error.message.en or "").strip()
    if not text:
        text = "ответ без текста"
    # W1: полный текст хранится в леджере (F5 показывает целиком); усечение —
    # только на компактном F1-рендере (format_qiki_voice_lines).

    legality_code = (
        f"{legality.status} [{legality.domain}] {legality.reason_code}" if legality is not None else None
    )
    trust_code = None
    if response.trust_signals:
        primary = response.trust_signals[0]
        trust_code = f"{primary.state} conf={primary.confidence:.2f}"

    return QikiVoiceEntry(
        received_at=received_at,
        kind=kind,
        text=text,
        legality_code=legality_code,
        trust_code=trust_code,
    )


def format_qiki_voice_lines(
    entries: Sequence[QikiVoiceEntry], *, limit: int = QIKI_VOICE_VISIBLE_LIMIT
) -> list[str]:
    recent = list(entries)[-limit:][::-1]  # хвост = новейшие; самая свежая — сверху

    def _compact(text: str) -> str:
        # F1 — 3-строчный компакт: режем длинный текст; F5 берёт полный из entry
        return text if len(text) <= _TEXT_MAX_CHARS else text[: _TEXT_MAX_CHARS - 1] + "…"

    return [f"QIKI ▸ {entry.received_at} {entry.kind} | {_compact(entry.text)}" for entry in recent]


def format_qiki_voice_tooltip(entries: Sequence[QikiVoiceEntry]) -> str | None:
    # Коды строго новейшей реплики — tooltip не смешивает эпохи диалога.
    for entry in reversed(list(entries)):
        parts = []
        if entry.legality_code:
            parts.append(f"LEGALITY {entry.legality_code}")
        if entry.trust_code:
            parts.append(f"TRUST {entry.trust_code}")
        return " · ".join(parts) if parts else None
    return None
