"""Этап 7 (G-F, Z3): строка идентичности QIKI на F1.

Канон-грунт (RAG 2026-07-09): идентичность QIKI = додекаэдрический корпус,
12 функциональных граней (bot_source_of_truth.md §корпус, READER_MANUAL §6
«модульность не создаёт нового робота»). Спека Z3: строка
`QIKI-<серийник> | додекаэдр · 12 граней | модулей N/12`, серийник — из
`hardware_profile_hash` (суррогат до появления отдельного id), evidence-мета
→ tooltip. Дом строки: статус-блок MFD — «кто я» видим ПОСТОЯННО (identity
не дублирует systems-страницу, решение №5 о дублях не нарушается).
"""

from __future__ import annotations

import pytest

from qiki.services.operator_console.orion_v.body_structure_view_model import (
    format_qiki_identity_line,
    format_qiki_identity_tooltip,
    get_body_structure_console_view_model,
)


def test_identity_line_with_serial_and_modules() -> None:
    vm = get_body_structure_console_view_model()
    line = format_qiki_identity_line(vm, hardware_profile_hash="3f2a9c77deadbeef")
    assert line.startswith("QIKI-3F2A9C ")
    assert "додекаэдр · 12 граней" in line
    assert f"модулей {vm.attached_modules_count}/{vm.faces_total}" in line


def test_identity_serial_skips_algorithm_prefix() -> None:
    """Канонный формат producer'а — "sha256:<64 hex>": серийник из digest,
    не «QIKI-SHA256» (поймано живым смоком)."""
    line = format_qiki_identity_line(
        get_body_structure_console_view_model(),
        hardware_profile_hash="sha256:207b23aaffee00112233445566778899",
    )
    assert line.startswith("QIKI-207B23 ")


def test_identity_line_without_serial_is_honest() -> None:
    """Нет hardware_profile_hash (нет телеметрии) — серийник честно «—»,
    не выдуманный."""
    line = format_qiki_identity_line(get_body_structure_console_view_model(), hardware_profile_hash=None)
    assert line.startswith("QIKI-— ")
    assert "додекаэдр · 12 граней" in line


def test_identity_tooltip_carries_evidence_meta() -> None:
    vm = get_body_structure_console_view_model()
    tooltip = format_qiki_identity_tooltip(vm, hardware_profile_hash="3f2a9c77deadbeef")
    assert "hardware_profile_hash" in tooltip  # источник серийника назван
    assert "суррогат" in tooltip  # честность: отдельного id нет
    assert vm.seed_status in tooltip or "посев" in tooltip  # evidence-мета


# ── Дом строки: статус-блок MFD кокпита ──────────────────────────────────────

def _capture_cockpit():
    pytest.importorskip("textual")
    from tests.unit.test_orion_v_cockpit import _CaptureCockpit

    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"hardware_profile_hash": "3f2a9c77deadbeef"},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    return screen


def test_status_block_shows_identity_when_right_mfd_is_systems() -> None:
    """Z3: «кто я» видим всегда — блок больше не схлопывается в пустоту при
    правом MFD «systems» (identity не дублирует systems-страницу)."""
    screen = _capture_cockpit()
    screen._active_right_mfd_page = "systems"
    text = screen._compose_mfd_status_text("")
    assert text.startswith("QIKI-3F2A9C ")
    assert "додекаэдр · 12 граней" in text
    # и НИКАКИХ body/physics/power сводок — они живут на systems-странице (№5)
    assert "Power(" not in text and "масса:" not in text


def test_status_block_identity_tops_summaries_on_other_pages() -> None:
    screen = _capture_cockpit()
    screen._active_right_mfd_page = "sensors"  # валидная right-страница ≠ systems
    text = screen._compose_mfd_status_text("")
    lines = text.splitlines()
    assert lines[0].startswith("QIKI-3F2A9C ")
    assert len(lines) >= 3  # identity + сводки body/physics/power


def test_status_block_identity_honest_without_telemetry() -> None:
    pytest.importorskip("textual")
    from tests.unit.test_orion_v_cockpit import _CaptureCockpit

    screen = _CaptureCockpit()
    screen.set_state(telemetry={}, nats_connected=True, active_incidents=0, incidents=[])
    screen._active_right_mfd_page = "systems"
    assert screen._compose_mfd_status_text("").startswith("QIKI-— ")
