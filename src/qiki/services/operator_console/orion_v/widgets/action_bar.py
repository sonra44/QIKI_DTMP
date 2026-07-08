from __future__ import annotations

from typing import Any

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Input, Static

from qiki.services.operator_console.orion_v.operator_state import OperatorShellState


class OrionVActionBar(Static):
    """Unified bottom action rail for navigation, feedback, and command mode."""

    DEFAULT_CSS = """
    OrionVActionBar {
        height: auto;
        layout: vertical;
    }

    OrionVActionBar #orionv-help {
        height: auto;
        max-height: 3;
        overflow-y: hidden;
        color: $text;
    }

    OrionVActionBar #orionv-console-strip {
        height: auto;
        color: $text-muted;
        padding: 0 1;
    }

    OrionVActionBar #orionv-command-strip,
    OrionVActionBar #orionv-action-buttons {
        height: auto;
        layout: horizontal;
    }

    OrionVActionBar #orionv-command-shell {
        width: 1fr;
        color: $text-muted;
        content-align: left middle;
    }

    OrionVActionBar #orionv-command-open {
        width: 18;
        min-width: 18;
        margin-left: 1;
    }

    OrionVActionBar #orionv-command {
        width: 1fr;
        min-width: 40;
    }

    OrionVActionBar #orionv-action-buttons Button {
        min-width: 8;
        height: 1;
        margin: 0 1 0 0;
    }
    """

    class ActionTriggered(Message):
        """Emitted when operator clicks an action button."""

        def __init__(self, action: str) -> None:
            self.action = action
            super().__init__()

    _BUTTONS: tuple[tuple[str, str], ...] = (
        ("f1", "F1 Кокпит"),
        ("f2", "F2 Системы"),
        ("f3", "F3 Анализ"),
        ("f4", "F4 Консоль"),
        ("f5", "F5 QIKI"),
        ("f6", "F6 Журнал"),
        ("f7", "F7 Статус"),
        ("f8", "F8 Улики"),
        ("incident_prev", "Инц <-"),
        ("incident_next", "Инц ->"),
        ("ack", "Подтв."),
        ("clear", "Снять"),
        ("page_prev", "< Стр"),
        ("page_next", "Стр >"),
        ("world_toggle", "⏸ Мир"),
        ("attach_toggle", "⏸ Установка"),
        ("qiki_confirm", "✓ Выполнить"),
        ("qiki_cancel", "✗ Отмена"),
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._state = OperatorShellState.empty()

    def compose(self) -> ComposeResult:
        yield Static("", id="orionv-help")
        yield Static("", id="orionv-console-strip")
        with Horizontal(id="orionv-command-strip"):
            yield Static("", id="orionv-command-shell")
            yield Button("Команда", id="orionv-command-open", compact=True)
            yield Input(placeholder="Введите команду (help)", id="orionv-command", classes="hidden")
        with Horizontal(id="orionv-action-buttons"):
            for action, label in self._BUTTONS:
                yield Button(label, id=f"orionv-action-{action}", compact=True)

    def on_mount(self) -> None:
        self._refresh_buttons()

    def set_state(self, state: OperatorShellState) -> None:
        self._state = state
        self._refresh_buttons()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if not button_id.startswith("orionv-action-"):
            return
        action = button_id.removeprefix("orionv-action-").strip().lower()
        if not action:
            return
        self.post_message(self.ActionTriggered(action))

    def _refresh_buttons(self) -> None:
        loop = self._state.operator_loop
        feedback = self.query_one("#orionv-help", Static)
        incident_text = loop.selected_incident_id or "none"
        subsystem_text = loop.selected_subsystem or "none"
        mode_text = "REPLAY" if loop.replay_mode else "LIVE"
        required_text = "required" if loop.operator_action_required else "standby"
        # plain Text, НЕ markup-строка: LLM-текст со скобками ([OPERATOR_HOLD])
        # не должен парситься (rich.escape не спасает — Textual-парсер ест и
        # «не-rich» теги; урок a58fd97: правда живёт в plain).
        feedback.update(Text(
            " | ".join(
                (
                    f"M {mode_text}",
                    f"L {loop.current_level.upper()}",
                    # CMD, not LOOP: this is the last-command status; "LOOP" collided
                    # with the F1 playable-loop phase and read as a contradiction
                    f"CMD {loop.last_command_status}",
                    f"P {loop.pending_command_count}",
                    f"ACT {required_text}",
                    f"INC {incident_text}",
                    f"MOD {subsystem_text}",
                    f"LAST {loop.last_command_summary}",
                )
            )
        ))

        console = self.query_one("#orionv-console-strip", Static)
        # На F5 лента диалога САМА показывает беседу/процедуру/реплики — стрип
        # КОНСОЛЬ там дублировал бы её (T5, один владелец). Прячем только на F5;
        # на остальных экранах стрип остаётся глобальным фидбеком (И3).
        if loop.current_level == "f5":
            console.display = False
        else:
            console.display = True
            console_lines = self._state.console_lines[-5:]
            if console_lines:
                rendered_lines = ["КОНСОЛЬ/CONSOLE"]
                rendered_lines.extend(f"- {escape(line)}" for line in console_lines)
                console.update("\n".join(rendered_lines))
            else:
                console.update("КОНСОЛЬ/CONSOLE: история пуста")

        shell = self.query_one("#orionv-command-shell", Static)
        shell.update(
            f"CMD {loop.command_mode_state.upper()}"
            f" | {loop.hotkey_context}"
        )
        shell.set_class(loop.command_mode_state == "open", "hidden")
        self.query_one("#orionv-command-open", Button).set_class(loop.command_mode_state == "open", "hidden")
        self.query_one("#orionv-command", Input).set_class(loop.command_mode_state != "open", "hidden")

        for action, _ in self._BUTTONS:
            button = self.query_one(f"#orionv-action-{action}", Button)
            if action in {"f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8"}:
                button.variant = "primary" if action == loop.current_level else "default"
                button.disabled = False
                continue

            if action in {"ack", "clear"}:
                # show-when (DISPLAY_CANON строка №9): без выбранного инцидента
                # кнопки скрыты, а не торчат серыми
                button.display = loop.incident_controls_visible and loop.has_selected_incident
                button.disabled = not button.display or loop.replay_mode
                button.variant = "warning" if action == "ack" else "default"
                continue

            if action in {"incident_prev", "incident_next"}:
                button.display = loop.incident_controls_visible and loop.has_selected_incident
                button.disabled = not button.display
                button.variant = "default"
                continue

            if action in {"page_prev", "page_next"}:
                button.display = loop.page_controls_visible
                button.disabled = not loop.page_controls_visible
                button.variant = "default"
                continue

            if action == "world_toggle":
                # Игровая пауза — постоянный операторский орган (виден всегда)
                button.display = True
                button.disabled = loop.replay_mode
                button.label = "▶ Мир" if loop.world_paused else "⏸ Мир"
                button.variant = "warning" if loop.world_paused else "default"
                continue

            if action == "attach_toggle":
                # ADR-0020: Пауза/Старт процедуры установки — show-when: активна
                button.display = loop.attach_procedure_active
                button.disabled = not loop.attach_procedure_active
                button.label = "▶ Установка" if loop.attach_procedure_paused else "⏸ Установка"
                button.variant = "warning" if loop.attach_procedure_paused else "default"
                continue

            if action in {"qiki_confirm", "qiki_cancel"}:
                # Срез 1 (F5-рука): подтверждение действия ПРЯМО на F5 — show-when:
                # есть кандидат (human_ack_required = qiki_pending_action ≠ None).
                # CaMeL: LLM-реплика идёт с proposals=[] → кандидата нет → кнопки нет.
                # Триггер дёргает канонический _confirm/_cancel (пломба/M5/M6 на пути).
                button.display = loop.qiki_action_pending
                if action == "qiki_confirm":
                    # действие телу — недоступно в режиме анализа истории
                    button.disabled = not loop.qiki_action_pending or loop.replay_mode
                    button.variant = "warning"
                else:
                    button.disabled = not loop.qiki_action_pending
                    button.variant = "default"
                continue

            button.display = True
            button.disabled = False
            button.variant = "default"
