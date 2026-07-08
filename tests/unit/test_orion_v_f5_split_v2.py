"""F5 экран пополам: чистая беседа слева | инфо-дисплей QIKI справа.

Решение оператора №1 цело: правая панель показывает АРТЕФАКТЫ QIKI
(кандидат, доверие/законность, решение-предпросмотр, улики) — то, что
приходит от неё; консольные данные не подписываются как «видение QIKI».
Контракты сохранены: rendered_text()/_styled_lines() — плоская правда
обеих колонок (старые тесты W1/W2/W7 живут без правок).
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from qiki.services.operator_console.orion_v.screens.qiki_dialog import (
    OrionVQikiDialogScreen,
    QikiDialogLine,
    TrustCard,
)


def _card() -> TrustCard:
    return TrustCard(
        action_title="Установить модуль",
        action_command="orionv.body ▸ attach.module",
        source="policy (кандидат)",
        legality_code="allowed [physics] BODY_ATTACH_READY",
        legality_status="allowed",
        trust_code="trusted conf=0.95",
    )


class _App(App[None]):
    def compose(self) -> ComposeResult:
        yield OrionVQikiDialogScreen(id="f5")


@pytest.mark.asyncio
async def test_split_two_columns_feed_left_panel_right() -> None:
    """Экран состоит из двух колонок: лента и панель — раздельные виджеты."""
    pytest.importorskip("textual")
    app = _App()
    async with app.run_test(size=(200, 40)) as pilot:
        await pilot.pause()
        screen = app.query_one("#f5", OrionVQikiDialogScreen)
        feed = screen.query_one("#qiki-dialog-feed", VerticalScroll)
        panel = screen.query_one("#qiki-vision-panel", VerticalScroll)

        screen.set_state(
            dialog_lines=[QikiDialogLine("06:00:10Z", "ОПЕРАТОР", "", "привет"),
                          QikiDialogLine("06:00:12Z", "QIKI", "INFO", "Готова.")],
            candidate_title="Установить модуль",
            candidate_command="orionv.body ▸ attach.module",
            decision_preview_lines=["шаг: q confirm"],
            trust_card=_card(),
        )
        await pilot.pause()

        assert feed is not panel  # физически разные виджеты

        # Лента: беседа есть, панельных зон нет
        ft = screen.feed_text()
        assert "── ДИАЛОГ ──" in ft and "Готова." in ft
        assert "КАНДИДАТ" not in ft and "ДОВЕРИЕ/ЗАКОННОСТЬ" not in ft

        # Панель: QIKI-артефакты есть, беседы нет
        pt = screen.panel_text()
        assert "── КАНДИДАТ ──" in pt and "── ДОВЕРИЕ/ЗАКОННОСТЬ ──" in pt
        assert "── УЛИКИ ──" in pt
        assert "Готова." not in pt


def test_rendered_text_contract_covers_both_columns() -> None:
    """Плоский rendered_text() несёт обе колонки — старые тесты живы."""
    screen = OrionVQikiDialogScreen()
    screen.set_state(
        dialog_lines=[QikiDialogLine("06:00:12Z", "QIKI", "INFO", "Готова.")],
        candidate_title="Установить модуль",
        decision_preview_lines=[],
        trust_card=_card(),
    )
    rendered = screen.rendered_text()
    assert "Готова." in rendered
    assert "КАНДИДАТ" in rendered
    assert "ДОВЕРИЕ/ЗАКОННОСТЬ" in rendered
    assert "УЛИКИ" in rendered


@pytest.mark.asyncio
async def test_feed_autoscrolls_to_latest_reply() -> None:
    """Свежий ответ QIKI виден без ручной прокрутки (лента прилипает к низу)."""
    pytest.importorskip("textual")
    app = _App()
    async with app.run_test(size=(120, 24)) as pilot:  # низкий экран → лента переполняется
        await pilot.pause()
        screen = app.query_one("#f5", OrionVQikiDialogScreen)
        lines = []
        for i in range(30):
            lines.append(QikiDialogLine(f"06:{i:02d}:00Z", "ОПЕРАТОР", "", f"вопрос {i}"))
            lines.append(QikiDialogLine(f"06:{i:02d}:30Z", "QIKI", "INFO", f"ответ номер {i}"))
        screen.set_state(dialog_lines=lines, candidate_title=None, decision_preview_lines=[])
        await pilot.pause()
        await pilot.pause()  # scroll_end уходит через call_after_refresh
        feed = screen.query_one("#qiki-dialog-feed", VerticalScroll)
        assert feed.max_scroll_y > 0  # контент реально переполнил колонку
        assert feed.scroll_offset.y == feed.max_scroll_y  # прилипли к последней реплике


def test_panel_shows_board_chips_with_hmi_style() -> None:
    """Правая панель наполнена: блок БОРТ из чипов мачты, отклонения крашены."""
    from qiki.services.operator_console.orion_v.operator_state import SubsystemChip

    chips = (
        SubsystemChip(slug="power", label="PWR", status="OK", severity="info",
                      short_summary="", hint="", anchor_text="100% ~262м"),
        SubsystemChip(slug="thermal", label="THRM", status="WARN", severity="warning",
                      short_summary="", hint="", anchor_text="74°"),
    )
    screen = OrionVQikiDialogScreen()
    screen.set_state(dialog_lines=[], candidate_title=None,
                     decision_preview_lines=[], board_chips=chips)
    pt = screen.panel_text()
    assert "БОРТ" in pt
    assert "PWR" in pt and "100% ~262м" in pt
    assert "THRM" in pt and "74°" in pt
    styles = {t: s for t, s in screen._flatten_blocks(screen._render_panel_blocks())}
    warn_row = next(t for t in styles if "THRM" in t)
    ok_row = next(t for t in styles if "PWR" in t)
    assert "yellow" in styles[warn_row]  # отклонение крашено
    assert "red" not in styles[ok_row] and "yellow" not in styles[ok_row]  # норма тиха


def test_panel_without_chips_has_no_empty_board_block() -> None:
    screen = OrionVQikiDialogScreen()
    screen.set_state(dialog_lines=[], candidate_title=None, decision_preview_lines=[])
    assert "БОРТ" not in screen.panel_text()


def test_thinking_indicator_show_when_pending() -> None:
    """«QIKI думает…» виден пока ждём ответ; исчезает с ответом."""
    screen = OrionVQikiDialogScreen()
    screen.set_state(
        dialog_lines=[QikiDialogLine("06:00:10Z", "ОПЕРАТОР", "", "расскажи о себе")],
        candidate_title=None, decision_preview_lines=[], thinking=True,
    )
    ft = screen.feed_text()
    assert "думает" in ft
    # индикатор стоит ПОСЛЕ последней реплики, до зоны ВВОД
    assert ft.index("расскажи о себе") < ft.index("думает") < ft.index("── ВВОД ──")

    screen.set_state(
        dialog_lines=[QikiDialogLine("06:00:10Z", "ОПЕРАТОР", "", "расскажи о себе"),
                      QikiDialogLine("06:00:50Z", "QIKI", "INFO", "Готова.")],
        candidate_title=None, decision_preview_lines=[], thinking=False,
    )
    assert "думает" not in screen.feed_text()
