"""Срез 1 (F5-рука): подтверждение действия ПРЯМО на F5 — кнопка в рельсе.

Инварианты:
- CaMeL: кнопка не появляется для LLM-кандидата (proposals=[] → нет pending).
- Переиспользование: кнопка дёргает канонический _confirm_qiki_pending_action,
  не изобретает второй execute-путь (пломба/M5/M6 остаются на пути).
- Провенанс/replay: в режиме анализа истории подтверждение недоступно.
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button

from qiki.services.operator_console.orion_v.operator_state import build_operator_shell_state
from qiki.services.operator_console.orion_v.widgets.action_bar import OrionVActionBar


class _ActionBarApp(App[None]):
    def compose(self) -> ComposeResult:
        yield OrionVActionBar(id="orionv-actions")


def _pending_action() -> dict:
    return {
        "title_ru": "Установить test_sensor → F09",
        "name": "attach.module",
        "subject": "orionv.body",
        "parameters": {"module_id": "test_sensor", "mount": "F09"},
        "action_kind": "BODY_ATTACH",
    }


@pytest.mark.asyncio
async def test_confirm_buttons_show_when_pending() -> None:
    """show-when: кнопки видны при активном кандидате, скрыты без него."""
    pytest.importorskip("textual")
    app = _ActionBarApp()
    async with app.run_test(size=(200, 20)) as pilot:
        await pilot.pause()
        actions = app.query_one("#orionv-actions", OrionVActionBar)

        # без кандидата — кнопок нет (не торчат серыми)
        actions.set_state(build_operator_shell_state(hardware_model=None, current_level="f5"))
        await pilot.pause()
        assert app.query_one("#orionv-action-qiki_confirm", Button).display is False
        assert app.query_one("#orionv-action-qiki_cancel", Button).display is False

        # есть кандидат (policy) — кнопки видны
        actions.set_state(build_operator_shell_state(
            hardware_model=None, current_level="f5",
            qiki_pending_action=_pending_action(),
            qiki_pending_action_title="Установить test_sensor → F09",
        ))
        await pilot.pause()
        assert app.query_one("#orionv-action-qiki_confirm", Button).display is True
        assert app.query_one("#orionv-action-qiki_cancel", Button).display is True
        assert app.query_one("#orionv-action-qiki_confirm", Button).disabled is False


@pytest.mark.asyncio
async def test_confirm_button_hidden_for_llm_candidate_camel() -> None:
    """CaMeL: LLM-реплика идёт с proposals=[] → qiki_pending_action=None →
    кнопки подтверждения НЕТ. Провайдер не может привести к действию через UI."""
    pytest.importorskip("textual")
    app = _ActionBarApp()
    async with app.run_test(size=(200, 20)) as pilot:
        await pilot.pause()
        actions = app.query_one("#orionv-actions", OrionVActionBar)
        # LLM-путь: pending отсутствует
        actions.set_state(build_operator_shell_state(
            hardware_model=None, current_level="f5", qiki_pending_action=None,
        ))
        await pilot.pause()
        assert app.query_one("#orionv-action-qiki_confirm", Button).display is False


@pytest.mark.asyncio
async def test_confirm_button_disabled_in_replay() -> None:
    """Режим анализа истории — подтверждение действия недоступно."""
    pytest.importorskip("textual")
    app = _ActionBarApp()
    async with app.run_test(size=(200, 20)) as pilot:
        await pilot.pause()
        actions = app.query_one("#orionv-actions", OrionVActionBar)
        actions.set_state(build_operator_shell_state(
            hardware_model=None, current_level="f5", replay_mode=True,
            qiki_pending_action=_pending_action(),
        ))
        await pilot.pause()
        assert app.query_one("#orionv-action-qiki_confirm", Button).disabled is True


def test_confirm_action_reuses_canonical_confirm_path() -> None:
    """Гейт: кнопка дёргает канонический _confirm/_cancel, не второй execute-путь."""
    from qiki.services.operator_console.orion_v.app import OrionVApp

    app = OrionVApp()
    calls: list[str] = []
    app._confirm_qiki_pending_action = lambda: calls.append("confirm")  # type: ignore[method-assign]
    app._cancel_qiki_pending_action = lambda: calls.append("cancel")  # type: ignore[method-assign]

    app._handle_action_bar_action("qiki_confirm")
    app._handle_action_bar_action("qiki_cancel")
    assert calls == ["confirm", "cancel"]
