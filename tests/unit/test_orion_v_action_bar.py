from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Input, Static

from qiki.services.operator_console.orion_v.operator_state import build_operator_shell_state
from qiki.services.operator_console.orion_v.widgets.action_bar import OrionVActionBar


class _ActionBarApp(App[None]):
    def compose(self) -> ComposeResult:
        yield OrionVActionBar(id="orionv-actions")


@pytest.mark.asyncio
async def test_action_bar_uses_compact_labels_for_dense_console_layout() -> None:
    pytest.importorskip("textual")

    app = _ActionBarApp()
    async with app.run_test(size=(180, 20)) as pilot:
        await pilot.pause()

        assert app.query_one("#orionv-action-f1", Button).label.plain == "F1 Кокпит"
        assert app.query_one("#orionv-action-f4", Button).label.plain == "F4 Консоль"
        assert app.query_one("#orionv-action-f8", Button).label.plain == "F8 Улики"
        assert app.query_one("#orionv-action-ack", Button).label.plain == "Подтв."
        assert app.query_one("#orionv-action-page_next", Button).label.plain == "Стр >"
        assert app.query_one("#orionv-command-open", Button).label.plain == "Команда"


@pytest.mark.asyncio
async def test_action_bar_hides_irrelevant_controls_outside_context() -> None:
    pytest.importorskip("textual")

    app = _ActionBarApp()
    async with app.run_test(size=(180, 20)) as pilot:
        await pilot.pause()

        actions = app.query_one("#orionv-actions", OrionVActionBar)
        actions.set_state(build_operator_shell_state(hardware_model=None, current_level="f2"))
        await pilot.pause()

        assert app.query_one("#orionv-action-incident_prev", Button).display is False
        assert app.query_one("#orionv-action-ack", Button).display is False
        assert app.query_one("#orionv-action-page_prev", Button).display is False

        actions.set_state(
            build_operator_shell_state(
                hardware_model=None,
                current_level="f3",
                selected_incident_id="inc-1",
                help_text="Incident selected",
                last_command_status="idle",
                last_command_summary="Incident selected",
            )
        )
        await pilot.pause()

        assert app.query_one("#orionv-action-incident_prev", Button).display is True
        assert app.query_one("#orionv-action-ack", Button).display is True
        assert app.query_one("#orionv-action-page_prev", Button).display is True
        assert app.query_one("#orionv-action-ack", Button).disabled is False
        feedback = app.query_one("#orionv-help", Static).render().plain
        assert "M LIVE" in feedback
        assert "CMD idle" in feedback  # last-command status (renamed from LOOP: collided with F1 playable loop)


@pytest.mark.asyncio
async def test_action_bar_disables_confirm_in_replay_mode() -> None:
    pytest.importorskip("textual")

    app = _ActionBarApp()
    async with app.run_test(size=(180, 20)) as pilot:
        await pilot.pause()

        actions = app.query_one("#orionv-actions", OrionVActionBar)
        actions.set_state(
            build_operator_shell_state(
                hardware_model=None,
                current_level="f3",
                replay_mode=True,
                selected_incident_id="inc-1",
            )
        )
        await pilot.pause()

        assert app.query_one("#orionv-action-ack", Button).disabled is True


@pytest.mark.asyncio
async def test_action_bar_switches_inline_command_mode() -> None:
    pytest.importorskip("textual")

    app = _ActionBarApp()
    async with app.run_test(size=(180, 20)) as pilot:
        await pilot.pause()

        actions = app.query_one("#orionv-actions", OrionVActionBar)
        command = app.query_one("#orionv-command", Input)
        shell = app.query_one("#orionv-command-shell", Static)

        assert command.has_class("hidden") is True
        assert shell.has_class("hidden") is False

        actions.set_state(
            build_operator_shell_state(
                hardware_model=None,
                current_level="f1",
                command_mode_open=True,
                help_text="Командный режим открыт",
                last_command_status="awaiting_qiki",
                last_command_summary="QIKI intent sent",
            )
        )
        await pilot.pause()

        assert command.has_class("hidden") is False
        assert shell.has_class("hidden") is True


@pytest.mark.asyncio
async def test_action_bar_renders_last_five_console_lines() -> None:
    pytest.importorskip("textual")

    app = _ActionBarApp()
    async with app.run_test(size=(180, 24)) as pilot:
        await pilot.pause()

        actions = app.query_one("#orionv-actions", OrionVActionBar)
        actions.set_state(
            build_operator_shell_state(
                hardware_model=None,
                console_lines=tuple(f"message {index}" for index in range(7)),
            )
        )
        await pilot.pause()

        strip = app.query_one("#orionv-console-strip", Static).render().plain
        assert "КОНСОЛЬ/CONSOLE" in strip
        assert "message 1" not in strip
        assert "message 2" in strip
        assert "message 6" in strip
