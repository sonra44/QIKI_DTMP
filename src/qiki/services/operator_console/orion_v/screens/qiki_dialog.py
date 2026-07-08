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

from textual.containers import VerticalScroll
from textual.widgets import Static

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.padding import Padding
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


@dataclass(frozen=True)
class TrustCard:
    """W2 (F5V2): Trust/Legality-карта текущего действия — «спина G1».

    И5: собирается ТОЛЬКО из локальных view-model (никакого provider-markdown);
    каждый ряд — готовый код из qiki_voice/legality, ноль новых деривов.
    """

    action_title: str
    action_command: str  # реальная команда телу (B1)
    source: str  # "провайдер (карантин)" | "policy" | ...
    legality_code: str  # "blocked [zone] ZONE_DENY" | "allowed [physics] ..."
    legality_status: str  # allowed|blocked|deferred|unsafe
    trust_code: str  # "degraded conf=0.62" | "trusted conf=0.95" | ""
    unlock_condition: str = ""  # G1 «условие допустимости»; пусто — строка скрыта


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
    """F5: свободная беседа с QIKI + её видение систем (read-only).

    F5V2-сплит: чистая лента беседы слева | инфо-дисплей QIKI справа
    (её артефакты: кандидат/доверие/решение/улики). Консольные данные
    не подписываются как «видение QIKI» (решение оператора №1).
    """

    DEFAULT_CSS = """
    OrionVQikiDialogScreen {
        layout: horizontal;
        height: 1fr;
    }
    OrionVQikiDialogScreen #qiki-dialog-feed {
        width: 2fr;
        height: 1fr;
        padding: 0 1;
    }
    OrionVQikiDialogScreen #qiki-vision-panel {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
        border-left: solid $surface-lighten-2;
    }
    OrionVQikiDialogScreen #qiki-dialog-feed-content,
    OrionVQikiDialogScreen #qiki-vision-panel-content {
        height: auto;
    }
    """

    def compose(self):
        # VerticalScroll, не Static с overflow: у Static виртуальный размер не
        # растёт с renderable (диагноз 2026-07-08: virtual=viewport, скролла нет).
        with VerticalScroll(id="qiki-dialog-feed"):
            yield Static("", id="qiki-dialog-feed-content")
        with VerticalScroll(id="qiki-vision-panel"):
            yield Static("", id="qiki-vision-panel-content")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._dialog_lines: list[QikiDialogLine] = []
        self._candidate_title: str | None = None
        self._candidate_command: str | None = None
        self._decision_preview_lines: list[str] = []
        self._trust_card: TrustCard | None = None
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
        trust_card: TrustCard | None = None,
    ) -> None:
        self._dialog_lines = list(dialog_lines)
        self._candidate_title = candidate_title
        self._candidate_command = candidate_command
        self._decision_preview_lines = list(decision_preview_lines)
        self._trust_card = trust_card
        self._refresh_text()

    def rendered_text(self) -> str:
        """Последний собранный текст экрана (для тестов и снапшотов)."""
        return self._last_text

    def feed_text(self) -> str:
        """Плоская правда ЛЕВОЙ колонки (беседа) — для тестов."""
        return "\n".join(t for t, _ in self._flatten_blocks(self._render_feed_blocks()))

    def panel_text(self) -> str:
        """Плоская правда ПРАВОЙ колонки (инфо-дисплей QIKI) — для тестов."""
        return "\n".join(t for t, _ in self._flatten_blocks(self._render_panel_blocks()))

    def _refresh_text(self) -> None:
        self._last_text = "\n".join(text for text, _ in self._styled_lines())
        # HMI-цвет через Rich-СПАНЫ + подсветка синтаксиса (W7): «line»-блоки —
        # Text.append(text, style) (НЕ парсит markup, коды в [скобках] живут); тело
        # QIKI — «md»-блок через rich.Markdown (код-фенс/списки подсвечены; коды в
        # скобках проверены — выживают). Норма приглушена, отклонения крашены.
        # F5V2-сплит: лента и панель рендерятся в СВОИ виджеты (2fr | 1fr).
        try:
            feed = self.query_one("#qiki-dialog-feed", VerticalScroll)
            # Прилипание к низу: свежая реплика видна БЕЗ ручной прокрутки;
            # если оператор ушёл вверх по истории — не дёргаем его.
            stick = feed.is_vertical_scroll_end
            self.query_one("#qiki-dialog-feed-content", Static).update(
                self._blocks_to_rich(self._render_feed_blocks())
            )
            self.query_one("#qiki-vision-panel-content", Static).update(
                self._blocks_to_rich(self._render_panel_blocks())
            )
            if stick:
                self.call_after_refresh(lambda: feed.scroll_end(animate=False))
        except Exception:  # noqa: BLE001 - NoActiveAppError/NoMatches и т.п.
            # вне смонтированного app (юнит-тесты) рендер не нужен;
            # правда текста живёт в rendered_text()/feed_text()/panel_text()
            pass

    def _blocks_to_rich(self, blocks: list[tuple[str, ...]]) -> RenderableType:
        """Собрать составной renderable: Text-спаны + Markdown-тело QIKI (W7)."""
        parts: list[RenderableType] = []
        buf = Text()
        buf_has = False

        def flush() -> None:
            nonlocal buf, buf_has
            if buf_has:
                parts.append(buf)
                buf = Text()
                buf_has = False

        for block in blocks:
            if block[0] == "md":
                flush()
                # отступ ┃-бара нет: Markdown-блок сам несёт визуальную структуру;
                # 2 пробела слева — асимметрия голоса QIKI (F5V2 §2 сохранена стампом).
                parts.append(Padding(Markdown(block[1]), pad=(0, 0, 0, 2)))
                continue
            _, text, style = block
            if buf_has:
                buf.append("\n")
            buf.append(text, style=style or None)
            buf_has = True
        flush()
        return Group(*parts) if parts else Text()

    # HMI-палитра (dark cockpit: норма приглушена, цвет — только отклонению)
    _HEADER_STYLE = "bold"
    _DIM = "dim"
    _KIND_STYLE = {"ACK": "green", "REJECT": "bold red", "INFO": ""}

    def _build_text(self) -> str:
        return "\n".join(text for text, _ in self._styled_lines())

    def _styled_lines(self) -> list[tuple[str, str]]:
        """Плоский (text, style) для rendered_text и тестов (обе колонки)."""
        return self._flatten_blocks(self._render_blocks())

    def _flatten_blocks(self, blocks: list[tuple[str, ...]]) -> list[tuple[str, str]]:
        """«line»-блоки — как есть; «md»-блок (тело QIKI) переносится в
        plain-строки индентом «  » (≤ ширины): снапшоты текстовые, коды живые."""
        out: list[tuple[str, str]] = []
        for block in blocks:
            if block[0] == "md":
                for wrapped in self._wrap_body(block[1], indent="  "):
                    out.append((wrapped, ""))
            else:
                out.append((block[1], block[2]))
        return out

    def _render_blocks(self) -> list[tuple[str, ...]]:
        """Полная блочная модель (лента + панель) — контракт rendered_text."""
        return self._render_feed_blocks() + [("line", "", "")] + self._render_panel_blocks()

    def _render_feed_blocks(self) -> list[tuple[str, ...]]:
        """ЛЕВАЯ колонка: чистая беседа. ("line", text, style) | ("md", md_source).

        «md» — только свободное тело реплики QIKI (И4: Markdown лишь для голоса,
        не для кодов/карты). Всё прочее — «line»-блоки с HMI-стилем.
        """
        out: list[tuple[str, ...]] = [
            ("line", "[F5] QIKI / ДИАЛОГ", self._HEADER_STYLE),
            ("line", "", ""),
        ]

        # Зона ДИАЛОГ (всегда).
        out.append(("line", "── ДИАЛОГ ──", self._HEADER_STYLE))
        if self._dialog_lines:
            for idx, line in enumerate(self._dialog_lines):
                if idx:
                    out.append(("line", "", ""))  # пустая строка между ходами (не рамки)
                speaker = line.speaker.upper()
                is_qiki = speaker.startswith("QIKI")
                is_procedure = speaker.startswith("ПРОЦЕДУРА")
                is_bot = is_qiki or is_procedure
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
                out.append(("line", head, head_style))
                if is_qiki:
                    # W7: свободное тело QIKI — Markdown-блок (подсветка синтаксиса);
                    # без ┃-бара, отступ даёт _blocks_to_rich (Padding).
                    out.append(("md", str(line.text)))
                else:
                    # ПРОЦЕДУРА — машинный леджер с ┃-баром; оператор — plain «  ».
                    indent = "┃ " if is_procedure else "  "
                    for wrapped in self._wrap_body(line.text, indent=indent):
                        out.append(("line", wrapped, ""))
                codes = self._codes_line(line)
                if codes:
                    out.append(("line", f"  └ {codes}", self._DIM))  # машинные факты — dim
        else:
            for ln in _EMPTY_DIALOG.splitlines():
                out.append(("line", ln, self._DIM))

        # Поле ввода на F5 открыто постоянно — подсказка dim (низ ленты).
        out.extend([("line", "", ""), ("line", "── ВВОД ──", self._HEADER_STYLE),
                    ("line", "печатайте QIKI и Enter · q confirm/abort — команды · Esc — снять фокус", self._DIM)])
        return out

    def _render_panel_blocks(self) -> list[tuple[str, ...]]:
        """ПРАВАЯ колонка: инфо-дисплей QIKI — её артефакты (кандидат, доверие,
        решение, улики). Консольные данные сюда НЕ подписываются как «видение
        QIKI» (решение оператора №1: её видение — её контур)."""
        out: list[tuple[str, ...]] = []

        # Зона КАНДИДАТ (show-when: есть предложение провайдера).
        if self._candidate_title:
            out.extend([("line", "── КАНДИДАТ ──", self._HEADER_STYLE),
                        ("line", self._candidate_title, "")])
            if self._candidate_command:
                out.append(("line", f"команда телу: {self._candidate_command}", self._DIM))
            out.append(("line", "источник: провайдер | candidate_only | НЕ исполняется", self._DIM))

        # W2: Trust/Legality-карта (show-when: есть текущее действие) — «спина G1».
        if self._trust_card is not None:
            card = self._trust_card
            if out:
                out.append(("line", "", ""))
            out.append(("line", "── ДОВЕРИЕ/ЗАКОННОСТЬ ──", self._HEADER_STYLE))
            out.append(("line", f"ДЕЙСТВИЕ      {card.action_title}", ""))
            if card.action_command:
                out.append(("line", f"команда телу  {card.action_command}", self._DIM))
            out.append(("line", f"ИСТОЧНИК      {card.source}", self._DIM))
            legality_style = "" if card.legality_status == "allowed" else (
                "bold red" if card.legality_status in {"blocked", "unsafe"} else "yellow"
            )
            out.append(("line", f"ЗАКОННОСТЬ    {card.legality_code}", legality_style))
            if card.trust_code:
                trust_style = "" if card.trust_code.startswith("trusted") else "yellow"
                out.append(("line", f"ДОВЕРИЕ       {card.trust_code}", trust_style))
            if card.unlock_condition:
                out.append(("line", f"РАЗБЛОКИРОВКА {card.unlock_condition}", "yellow"))

        # Зона РЕШЕНИЕ-предпросмотр (show-when: есть кандидат).
        if self._decision_preview_lines:
            out.append(("line", "", ""))
            out.append(("line", "── РЕШЕНИЕ (предпросмотр) ──", self._HEADER_STYLE))
            for ln in self._decision_preview_lines:
                out.append(("line", ln, ""))

        # Зона УЛИКИ (всегда) — dim-указатель.
        if out:
            out.append(("line", "", ""))
        out.extend([("line", "── УЛИКИ ──", self._HEADER_STYLE),
                    ("line", "детали: F8 | журнал: F6 | системы: F2", self._DIM)])
        return out

    _WRAP_WIDTH = 110

    def _wrap_body(self, text: str, *, indent: str = "  ") -> list[str]:
        """Перенос тела реплики по ширине колонки, сохраняя слова и абзацы."""
        out: list[str] = []
        for paragraph in str(text).split("\n"):
            cur = indent
            has_word = False  # был ли на текущей строке хоть один word (не пробел от индента)
            for word in [w for w in paragraph.split(" ") if w]:
                if has_word and len(cur) + 1 + len(word) > self._WRAP_WIDTH:
                    out.append(cur)
                    cur = indent + word
                else:
                    cur = (cur + " " + word) if has_word else (indent + word)
                has_word = True
            out.append(cur if has_word else indent.rstrip())
        return out or [indent.rstrip()]

    @staticmethod
    def _codes_line(line: QikiDialogLine) -> str:
        parts: list[str] = []
        if line.legality_code:
            parts.append(f"LEGALITY {line.legality_code}")
        if line.trust_code:
            parts.append(f"TRUST {line.trust_code}")
        return " · ".join(parts)
