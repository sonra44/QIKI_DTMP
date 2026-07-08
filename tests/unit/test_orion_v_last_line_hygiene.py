"""Гигиена статус-строки: длинный ответ QIKI не съедает экран.

По живому инциденту 2026-07-08: свободный Mercury выдал 4000-токенный
markdown-отчёт → он целиком лёг в LAST рельса → ACTION RAIL занял ~85%
экрана F2, контент уровня схлопнулся, кнопки уехали за низ терминала.
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.operator_state import build_operator_shell_state
from qiki.services.operator_console.orion_v.widgets.action_bar import OrionVActionBar

LONG_MD = "**QIKI отчёт**\n\n| Параметр | Значение |\n|---|---|\n" + "\n".join(
    f"| параметр {i} | значение {i} |" for i in range(60)
)


def _app() -> OrionVApp:
    app = OrionVApp()
    app._request_refresh_ui = lambda: None  # type: ignore
    return app


def test_reply_ready_summary_is_short_pointer() -> None:
    """Ответ бота НЕ льётся в LAST: короткий указатель «ответ готов — F5»."""
    app = _app()
    app._set_last_command_loop_state = OrionVApp._set_last_command_loop_state.__get__(app)
    # эмулируем ветку reply_ready как в _on_qiki_response
    from qiki.shared.models.qiki_chat import BilingualText, QikiReplyV1
    reply = QikiReplyV1(title=BilingualText(en="QIKI", ru="QIKI"),
                        body=BilingualText(en=LONG_MD, ru=LONG_MD))
    app._apply_reply_ready_status(reply)
    assert len(app._last_command_summary) <= 60
    assert "F5" in app._last_command_summary
    assert "**" not in app._last_command_summary


def test_status_setter_caps_any_source() -> None:
    """Защитный инвариант: любой источник — первая строка + жёсткий кап."""
    app = _app()
    app._set_last_command_loop_state("reply_ready", LONG_MD)
    assert "\n" not in app._last_command_summary
    assert len(app._last_command_summary) <= 121  # 120 + многоточие


def test_help_setter_caps_any_source() -> None:
    """Help/консольная история не принимают простыню: одна строка + кап."""
    app = _app()
    app._set_help_text(f"QIKI: {LONG_MD}")
    assert "\n" not in app._help_text
    assert len(app._help_text) <= 161
    assert all("\n" not in item for item in app._console_history)


@pytest.mark.asyncio
async def test_action_bar_escapes_last_summary_markup() -> None:
    """LLM-текст со скобками не парсится как разметка (и не роняет виджет)."""
    pytest.importorskip("textual")

    class _BarApp(App[None]):
        def compose(self) -> ComposeResult:
            yield OrionVActionBar(id="orionv-actions")

    app = _BarApp()
    async with app.run_test(size=(200, 20)) as pilot:
        await pilot.pause()
        actions = app.query_one("#orionv-actions", OrionVActionBar)
        actions.set_state(build_operator_shell_state(
            hardware_model=None,
            last_command_status="reply_ready",
            last_command_summary="код [OPERATOR_HOLD] и [red]boom[/red] остаются текстом",
        ))
        await pilot.pause()
        plain = app.query_one("#orionv-help", Static).render().plain
        assert "[OPERATOR_HOLD]" in plain  # скобки — буквальный текст
        assert "[red]boom[/red]" in plain  # markup не исполнен


@pytest.mark.asyncio
async def test_help_strip_has_height_ceiling() -> None:
    """CSS-страховка: статус-строке физически нельзя съесть экран."""
    pytest.importorskip("textual")

    class _BarApp(App[None]):
        def compose(self) -> ComposeResult:
            yield OrionVActionBar(id="orionv-actions")

    app = _BarApp()
    async with app.run_test(size=(200, 24)) as pilot:
        await pilot.pause()
        help_widget = app.query_one("#orionv-help", Static)
        assert help_widget.styles.max_height is not None
        assert int(help_widget.styles.max_height.value) <= 4
