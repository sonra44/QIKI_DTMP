"""UI P2/P3 (второй проход пост-ревью): рейл, палитра, лейблы, глифы.

Находки свежей верификации субагентом (детали первого ревью утеряны):
рейл ACTION RAIL был одноцветным (Text без спанов); header красил коды
ANSI-именами терминала вместо палитры пульта; refresh перезаписывал русские
«Панель ▲/▼» английскими «Panel ▲/▼» (B1); три вокабуляра стрелок.
"""

from __future__ import annotations

import pytest

from qiki.services.operator_console.orion_v.operator_state import (
    OperatorLoopState,
    OperatorShellState,
)
from qiki.services.operator_console.orion_v.ui_rich import ORION_UI_COLORS
from qiki.services.operator_console.orion_v.widgets.action_bar import (
    OrionVActionBar,
    build_action_rail_text,
)


# ── P2: семантические спаны ACTION RAIL ──────────────────────────────────────

def test_action_rail_carries_semantic_spans() -> None:
    loop = OperatorLoopState(
        last_command_status="failed",
        pending_command_count=2,
        operator_action_required=True,
        selected_incident_id="INC-1",
    )
    rail = build_action_rail_text(loop)
    styles = {str(span.style) for span in rail.spans}
    assert styles, "рейл без единого спана — вся строка одноцветная (P2)"
    assert ORION_UI_COLORS["crit"] in styles  # CMD failed
    assert ORION_UI_COLORS["warn"] in styles  # P 2 / ACT required / INC
    assert ORION_UI_COLORS["ok"] in styles  # M LIVE
    assert "M LIVE" in rail.plain and "CMD failed" in rail.plain


def test_action_rail_unknown_status_stays_plain() -> None:
    """Незнакомый статус не гадается: значение остаётся plain."""
    loop = OperatorLoopState(last_command_status="quantum_flux")
    rail = build_action_rail_text(loop)
    assert "CMD quantum_flux" in rail.plain
    crit_or_ok = {ORION_UI_COLORS["crit"], ORION_UI_COLORS["ok"], ORION_UI_COLORS["warn"]}
    value_styles = {
        str(span.style)
        for span in rail.spans
        if rail.plain[span.start:span.end] == "quantum_flux"
    }
    assert not (value_styles & crit_or_ok)


def test_action_rail_is_plain_text_not_markup() -> None:
    """Урок a58fd97: скобки LLM-текста не должны парситься как markup."""
    loop = OperatorLoopState(last_command_summary="hold [OPERATOR_HOLD] active")
    rail = build_action_rail_text(loop)
    assert "[OPERATOR_HOLD]" in rail.plain


# ── P3: header красит коды палитрой пульта, не ANSI-именами ──────────────────

def test_header_uses_orion_palette_not_ansi_names() -> None:
    pytest.importorskip("textual")
    from qiki.services.operator_console.orion_v.widgets.header import OrionVHeader

    header = OrionVHeader()
    captured: list[str] = []
    header.update = lambda content="": captured.append(str(content))  # type: ignore[method-assign]
    header.set_state(OperatorShellState.empty())
    assert captured, "стрип не обновился"
    rendered = captured[-1]
    for ansi_name in ("[green]", "[yellow]", "[red]", "[cyan]"):
        assert ansi_name not in rendered, f"ANSI-имя {ansi_name} в стрипе (P3)"
    palette_hexes = {ORION_UI_COLORS["ok"], ORION_UI_COLORS["warn"], ORION_UI_COLORS["crit"]}
    assert any(hex_color in rendered for hex_color in palette_hexes), rendered


# ── B1: лейблы focus-кнопок — один владелец, русский пульт ───────────────────

def test_focus_button_labels_single_russian_owner() -> None:
    pytest.importorskip("textual")
    from qiki.services.operator_console.orion_v.screens.cockpit import (
        COCKPIT_FOCUS_NEXT_LABEL,
        COCKPIT_FOCUS_PREV_LABEL,
    )

    assert COCKPIT_FOCUS_PREV_LABEL == "Панель ▲"
    assert COCKPIT_FOCUS_NEXT_LABEL == "Панель ▼"
    # регрессия B1: английские литералы в модуле недопустимы
    import inspect

    from qiki.services.operator_console.orion_v.screens import cockpit

    source = inspect.getsource(cockpit)
    assert "Panel ▲" not in source and "Panel ▼" not in source


# ── P3: один вокабуляр стрелок ───────────────────────────────────────────────

def test_arrow_glyphs_are_consistent() -> None:
    labels = dict(OrionVActionBar._BUTTONS)
    assert labels["incident_prev"] == "Инц ←"
    assert labels["incident_next"] == "Инц →"
    assert labels["page_prev"] == "← Стр"
    assert labels["page_next"] == "Стр →"
    joined = " ".join(labels.values())
    assert "<-" not in joined and "->" not in joined
    assert "< " not in joined and " >" not in joined
