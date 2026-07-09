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

import dataclasses

from qiki.services.operator_console.orion_v.body_structure_view_model import (
    build_body_structure_self_check_view_model,
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


def test_identity_module_count_reads_from_vm() -> None:
    """Аудит 0049 (HIGH): сид всегда давал 0 модулей — хардкод «модулей 0/12»
    выживал все тесты. Реальный attach-пайплайн даёт N=1."""
    vm = build_body_structure_self_check_view_model()
    assert vm.attached_modules_count == 1  # настоящий attach, не фикстура
    line = format_qiki_identity_line(vm, hardware_profile_hash="sha256:abcdef99")
    assert "модулей 1/12" in line


def test_identity_canon_faces_survive_broken_seed() -> None:
    """Аудит 0049 (F1): «12 граней» — канон идентичности, не состояние
    посева; сломанный посев (faces_total=0) не рождает «додекаэдр · 0 граней»."""
    vm = dataclasses.replace(
        get_body_structure_console_view_model(), faces_total=0, attached_modules_count=0
    )
    line = format_qiki_identity_line(vm, hardware_profile_hash=None)
    assert "додекаэдр · 12 граней" in line
    assert "модулей 0/12" in line
    assert "0 граней" not in line


def test_identity_non_string_hash_is_rejected() -> None:
    """Аудит 0049 (F4): dict/list из битой телеметрии давали мусорный
    серийник через str()-коэрцию."""
    vm = get_body_structure_console_view_model()
    for garbage in ({"x": 1}, ["a"], 12345):
        line = format_qiki_identity_line(vm, hardware_profile_hash=garbage)  # type: ignore[arg-type]
        assert line.startswith("QIKI-— "), line


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
    правом MFD «systems» (identity не дублирует systems-страницу).
    Аудит 0049 (MED): блок при systems — РОВНО identity-строка (раньше
    стереглись только Power/масса — протечка body-сводки прошла бы)."""
    screen = _capture_cockpit()
    screen._active_right_mfd_page = "systems"
    text = screen._compose_mfd_status_text("")
    lines = text.splitlines()
    assert len(lines) == 1, f"при systems блок должен нести ровно identity: {lines}"
    assert lines[0].startswith("QIKI-3F2A9C ")
    assert "додекаэдр · 12 граней" in lines[0]


def test_status_block_tooltip_is_wired_in_live_cockpit() -> None:
    """Аудит 0049 (HIGH): проводка tooltip не была в гейте — мутация
    «tooltip=""» выживала (её ловил только не-гейтовый смок)."""
    pytest.importorskip("textual")
    import asyncio

    from textual.widgets import Static

    from qiki.services.operator_console.orion_v.app import OrionVApp

    async def _run() -> str:
        app = OrionVApp()
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.pause()
            return str(app.query_one("#orionv-mfd-status", Static).tooltip or "")

    tooltip = asyncio.run(_run())
    # без телеметрии серийника нет — но evidence-мета обязана стоять
    assert "суррогат" in tooltip and "hardware_profile_hash" in tooltip, tooltip


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
