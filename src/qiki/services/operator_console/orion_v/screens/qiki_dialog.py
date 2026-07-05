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

from rich.text import Text

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
    procedure_lines: Sequence[tuple[str, str]] = (),
) -> list[QikiDialogLine]:
    """Свести реплики оператора, голос QIKI и записи процедуры в одну ленту.

    Один владелец на каждый источник: operator_lines — intent-лог оператора,
    voice_entries — leджер qiki_voice (№8в), procedure_lines — стадии установки
    (ADR-0020 §6: НЕ голос QIKI — отдельный говорящий «ПРОЦЕДУРА»).
    """
    merged: list[QikiDialogLine] = [
        QikiDialogLine(received_at=ts, speaker="ОПЕРАТОР", kind="", text=text)
        for ts, text in operator_lines
    ]
    merged.extend(
        QikiDialogLine(received_at=ts, speaker="ПРОЦЕДУРА", kind="", text=text)
        for ts, text in procedure_lines
    )
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
        self._candidate_command: str | None = None
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
        candidate_command: str | None = None,
    ) -> None:
        self._dialog_lines = list(dialog_lines)
        self._candidate_title = candidate_title
        self._candidate_command = candidate_command
        self._decision_preview_lines = list(decision_preview_lines)
        self._refresh_text()

    def rendered_text(self) -> str:
        """Последний собранный текст экрана (для тестов и снапшотов)."""
        return self._last_text

    def _refresh_text(self) -> None:
        lines = self._styled_lines()
        self._last_text = "\n".join(text for text, _ in lines)
        # HMI-цвет через Rich-СПАНЫ: Text.append(text, style) НЕ парсит markup —
        # коды в [скобках] остаются кодами (инвариант plain-режима сохранён),
        # но норма приглушена, отклонения крашены (ISA-101 / DISPLAY_CANON T7).
        try:
            rich = Text()
            for idx, (text, style) in enumerate(lines):
                if idx:
                    rich.append("\n")
                rich.append(text, style=style or None)
            self.update(rich)
        except Exception:  # noqa: BLE001 - NoActiveAppError и т.п.
            # вне смонтированного app (юнит-тесты) рендер не нужен;
            # правда текста живёт в rendered_text()
            pass

    # HMI-палитра (dark cockpit: норма приглушена, цвет — только отклонению)
    _HEADER_STYLE = "bold"
    _DIM = "dim"
    _KIND_STYLE = {"ACK": "green", "REJECT": "bold red", "INFO": ""}

    def _build_text(self) -> str:
        return "\n".join(text for text, _ in self._styled_lines())

    def _styled_lines(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = [("[F5] QIKI / ДИАЛОГ", self._HEADER_STYLE), ("", "")]

        # Зона ДИАЛОГ (всегда).
        out.append(("── ДИАЛОГ ──", self._HEADER_STYLE))
        if self._dialog_lines:
            for idx, line in enumerate(self._dialog_lines):
                if idx:
                    out.append(("", ""))  # пустая строка между ходами (не рамки)
                speaker = line.speaker.upper()
                is_bot = speaker.startswith("QIKI") or speaker.startswith("ПРОЦЕДУРА")
                if is_bot:
                    # штамп QIKI/ПРОЦЕДУРА — полный HH:MM:SSZ (канон 8в: freshness)
                    head = f"{line.speaker} ▸ {line.received_at}"
                    if line.kind:
                        head += f" {line.kind}"
                else:
                    # оператор — компактный «я ▸ HH:MM» (F5V2 §2, асимметрия)
                    head = f"я ▸ {line.received_at[:5]}"
                # Заголовок QIKI крашен по типу арбитража (REJECT красный, ACK
                # зелёный, INFO нейтральный); оператор — нейтральный.
                head_style = self._KIND_STYLE.get(line.kind or "", "") if is_bot else ""
                out.append((head, head_style))
                indent = "┃ " if is_bot else "  "
                for wrapped in self._wrap_body(line.text, indent=indent):
                    out.append((wrapped, ""))
                codes = self._codes_line(line)
                if codes:
                    out.append((f"  └ {codes}", self._DIM))  # машинные факты — dim
        else:
            for ln in _EMPTY_DIALOG.splitlines():
                out.append((ln, self._DIM))

        # Зона КАНДИДАТ (show-when: есть предложение провайдера).
        if self._candidate_title:
            out.extend([("", ""), ("── КАНДИДАТ ──", self._HEADER_STYLE), (self._candidate_title, "")])
            if self._candidate_command:
                out.append((f"команда телу: {self._candidate_command}", self._DIM))
            out.append(("источник: провайдер | candidate_only | НЕ исполняется", self._DIM))

        # Зона РЕШЕНИЕ-предпросмотр (show-when: есть кандидат).
        if self._decision_preview_lines:
            out.append(("", ""))
            out.append(("── РЕШЕНИЕ (предпросмотр) ──", self._HEADER_STYLE))
            for ln in self._decision_preview_lines:
                out.append((ln, ""))

        # Зона УЛИКИ (всегда) — dim-указатель.
        out.extend([("", ""), ("── УЛИКИ ──", self._HEADER_STYLE),
                    ("детали: F8 | журнал: F6 | системы: F2", self._DIM)])

        # Поле ввода на F5 открыто постоянно — подсказка dim.
        out.extend([("", ""), ("── ВВОД ──", self._HEADER_STYLE),
                    ("печатайте QIKI и Enter · q confirm/abort — команды · Esc — снять фокус", self._DIM)])
        return out

    _WRAP_WIDTH = 110

    def _wrap_body(self, text: str, *, indent: str = "  ") -> list[str]:
        """Перенос тела реплики по ширине колонки, сохраняя слова и абзацы."""
        out: list[str] = []
        for paragraph in str(text).split("\n"):
            words = paragraph.split(" ")
            cur = indent
            for word in words:
                if len(cur) + len(word) + 1 > self._WRAP_WIDTH and cur.strip():
                    out.append(cur.rstrip())
                    cur = indent + word
                else:
                    cur = (cur + " " + word) if cur.strip() else (indent + word)
            out.append(cur.rstrip() or indent.rstrip())
        return out or [indent.rstrip()]

    @staticmethod
    def _codes_line(line: QikiDialogLine) -> str:
        parts: list[str] = []
        if line.legality_code:
            parts.append(f"LEGALITY {line.legality_code}")
        if line.trust_code:
            parts.append(f"TRUST {line.trust_code}")
        return " · ".join(parts)
