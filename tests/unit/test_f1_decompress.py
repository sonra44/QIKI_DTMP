"""Этап 5 «f1-decompress» (фаза G-A): дефолт обучалки, Краткие факты, подписи.

По `03_F1_COCKPIT_SPEC.md` (Z5-Z8) и `09_WORK_SEQUENCE.md` (этап 5).
Z9 (show-when кнопок инцидентов) и снятие acceptance-чеклиста сделаны ранее
(DISPLAY_CANON №8/№9) — здесь только пины на их сохранение.
"""

from __future__ import annotations

from qiki.services.operator_console.orion_v.body_structure_view_model import (
    format_body_structure_cockpit_line,
)
from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    reset_body_structure_interactive_state,
)
from qiki.services.operator_console.orion_v.body_structure_view_model import (
    get_body_structure_console_view_model,
)
from qiki.services.operator_console.orion_v.body_physics_view_model import (
    get_body_physics_console_view_model,
)
from qiki.services.operator_console.orion_v.cockpit_playable_view_model import (
    build_cockpit_playable_loop_vm,
    build_cockpit_playable_state,
    format_cockpit_playable_loop_lines,
)
from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    build_power_thermal_console_view_model_from_telemetry,
)
from qiki.services.operator_console.orion_v.screens.cockpit import (
    MFD_PAGE_SWITCH_SUBTITLE,
    OrionVCockpitScreen,
)


def setup_function() -> None:
    reset_body_structure_interactive_state()


def _loop_lines(**state_kwargs) -> str:
    body = get_body_structure_console_view_model()
    physics = get_body_physics_console_view_model(body)
    power = build_power_thermal_console_view_model_from_telemetry({})
    state = build_cockpit_playable_state(selected_action_id="power_refresh", **state_kwargs)
    vm = build_cockpit_playable_loop_vm(
        loop_state=state,
        body_vm=body,
        body_physics_vm=physics,
        power_vm=power,
        active_left_mfd_page="radar",
        active_right_mfd_page="systems",
        nats_connected=False,
        active_incidents=0,
    )
    return "\n".join(format_cockpit_playable_loop_lines(vm))


# ── Z7: обучалка по умолчанию скрыта (dark cockpit), H включает ─────────────

def test_help_hidden_by_default() -> None:
    lines = _loop_lines()
    assert "КЛАВИШИ |" not in lines
    assert "ПАЛИТРА | Ctrl+P" not in lines
    assert "цикл: снимок" not in lines
    assert "H — справка | Ctrl+P — палитра" in lines  # одна строка-подсказка


def test_help_on_shows_training_block() -> None:
    lines = _loop_lines(help_visible=True)
    assert "КЛАВИШИ |" in lines
    assert "цикл: снимок → экран → предпросмотр → запрос → применение → событие → улика" in lines


# ── Z8: «Краткие факты» — только непустые, пустые схлопнуты одной строкой ────

def test_quick_facts_collapse_empty_groups() -> None:
    screen = OrionVCockpitScreen()
    rows = screen.build_quick_fact_rows(
        [
            ("SAFETY", "ok", ("", "—")),
            ("ENERGY", "warn", ("Заряд 80%", "")),
            ("THERMAL", "ok", ("—",)),
        ]
    )
    joined = "\n".join(rows)
    assert "ENERGY" in joined and "Заряд 80%" in joined
    assert "нет данных: SAFETY, THERMAL" in joined
    assert joined.count("—") == 0  # рядов-пустышек больше нет


# ── Z8: заголовок корпуса — русский, не BODY STRUCTURE ──────────────────────

def test_body_structure_header_localized() -> None:
    line = format_body_structure_cockpit_line()
    assert line.startswith("КОРПУС (посев)")
    assert "BODY STRUCTURE" not in line


# ── Z6-подпись: рамки MFD несут подсказку переключения страниц ───────────────

def test_mfd_page_switch_subtitle_wording() -> None:
    assert MFD_PAGE_SWITCH_SUBTITLE == "перекл. страниц: [ / ]"
