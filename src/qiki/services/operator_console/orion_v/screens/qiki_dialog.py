"""F5 «QIKI / ДИАЛОГ» — экран свободной беседы с QIKI (read-only, M1).

Дизайн: docs/design/operator_console/F5_QIKI_DIALOG_SYSTEM_DESIGN.md §5.
Зоны: ДИАЛОГ / КАНДИДАТ (show-when) / РЕШЕНИЕ-предпросмотр (show-when) / УЛИКИ.

M1 read-only: экран только ОТОБРАЖАЕТ существующее состояние (лента qiki_voice +
реплики оператора из intent-лога, кандидат из _qiki_pending_action). Он НЕ
добавляет пути исполнения: ввод остаётся в command mode, подтверждение — на
кокпите (q confirm). Кандидат помечен candidate_only / «НЕ исполняется» (ADR-0015:
текст провайдера ≠ pending action ≠ effect).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from textual.widgets import Static

from qiki.services.operator_console.orion_v.qiki_voice import QikiVoiceEntry

_EMPTY_DIALOG = (
    "QIKI — не внешний чат-бот. Ответ провайдера — только кандидат.\n"
    "q: <запрос> — начать диалог."
)


@dataclass(frozen=True)
class QikiDialogLine:
    """Одна реплика ленты диалога, уже разобранная владельцем данных."""

    received_at: str  # "HH:MM:SSZ" (UTC)
    speaker: str  # "ОПЕРАТОР" | "QIKI"
    kind: str  # "" | "ACK" | "REJECT" | "INFO"
    text: str
    legality_code: str | None = None
    trust_code: str | None = None


def merge_dialog_lines(
    *,
    operator_lines: Sequence[tuple[str, str]],
    voice_entries: Sequence[QikiVoiceEntry],
) -> list[QikiDialogLine]:
    """Свести реплики оператора и голос QIKI в одну ленту по времени приёма.

    Один владелец на каждый источник: operator_lines — intent-лог оператора,
    voice_entries — leджер qiki_voice (№8в). Новых деривов не создаём.
    """
    merged: list[QikiDialogLine] = [
        QikiDialogLine(received_at=ts, speaker="ОПЕРАТОР", kind="", text=text)
        for ts, text in operator_lines
    ]
    merged.extend(
        QikiDialogLine(
            received_at=entry.received_at,
            speaker="QIKI",
            kind=entry.kind,
            text=entry.text,
            legality_code=entry.legality_code,
            trust_code=entry.trust_code,
        )
        for entry in voice_entries
    )
    # Стабильная сортировка по строковому HH:MM:SSZ (общий UTC-формат обоих источников).
    merged.sort(key=lambda line: line.received_at)
    return merged


class OrionVQikiDialogScreen(Static):
    """F5: свободная беседа с QIKI + её видение систем (read-only)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._dialog_lines: list[QikiDialogLine] = []
        self._candidate_title: str | None = None
        self._decision_preview_lines: list[str] = []
        self._last_text: str = ""

    def on_mount(self) -> None:
        self._refresh_text()

    def set_state(
        self,
        *,
        dialog_lines: Sequence[QikiDialogLine],
        candidate_title: str | None,
        decision_preview_lines: Sequence[str],
    ) -> None:
        self._dialog_lines = list(dialog_lines)
        self._candidate_title = candidate_title
        self._decision_preview_lines = list(decision_preview_lines)
        self._refresh_text()

    def rendered_text(self) -> str:
        """Последний собранный текст экрана (для тестов и снапшотов)."""
        return self._last_text

    def _refresh_text(self) -> None:
        self._last_text = self._build_text()
        self.update(self._last_text)

    def _build_text(self) -> str:
        body: list[str] = ["[F5] QIKI / ДИАЛОГ", ""]

        # Зона ДИАЛОГ (всегда).
        body.append("── ДИАЛОГ ──")
        if self._dialog_lines:
            for line in self._dialog_lines:
                head = f"{line.speaker} ▸ {line.received_at}"
                if line.kind:
                    head += f" {line.kind}"
                body.append(f"{head} | {line.text}")
                codes = self._codes_line(line)
                if codes:
                    body.append(f"  └ {codes}")
        else:
            body.extend(_EMPTY_DIALOG.splitlines())

        # Зона КАНДИДАТ (show-when: есть предложение провайдера).
        if self._candidate_title:
            body.extend(
                [
                    "",
                    "── КАНДИДАТ ──",
                    self._candidate_title,
                    "источник: провайдер | candidate_only | НЕ исполняется",
                ]
            )

        # Зона РЕШЕНИЕ-предпросмотр (show-when: есть кандидат).
        if self._decision_preview_lines:
            body.append("")
            body.append("── РЕШЕНИЕ (предпросмотр) ──")
            body.extend(self._decision_preview_lines)

        # Зона УЛИКИ (всегда).
        body.extend(["", "── УЛИКИ ──", "детали: F8 | журнал: F6 | системы: F2"])

        return "\n".join(body)

    @staticmethod
    def _codes_line(line: QikiDialogLine) -> str:
        parts: list[str] = []
        if line.legality_code:
            parts.append(f"LEGALITY {line.legality_code}")
        if line.trust_code:
            parts.append(f"TRUST {line.trust_code}")
        return " · ".join(parts)
