from __future__ import annotations

import pytest

pytest.importorskip("textual")

from textual.app import App, ComposeResult

from qiki.services.operator_console.orion_v.screens.evidence_stream import (
    OrionVEvidenceScreen,
    _render_evidence_detail_mfd,
    _render_evidence_list_mfd,
    build_evidence_card_vms,
)


_POWER_SNAPSHOT = {
    "source": "q_sim_service.world_model.power",
    "power": {
        "soc_pct": 42.0,
        "supercap_soc_pct": 79.0,
        "bus_v": 28.0,
        "bus_a": 1.25,
        "loads_w": {"base": 10.0},
        "sources_w": {"solar": 40.0},
    },
}


def _power_index(cards) -> int:
    for index, card in enumerate(cards):
        if card.subsystem == "ПИТАНИЕ/НАКОПИТЕЛИ":
            return index
    raise AssertionError("карточка ПИТАНИЕ/НАКОПИТЕЛИ не найдена")


def test_f8_detail_renders_selected_power_card_not_first_body_card() -> None:
    cards = build_evidence_card_vms(_POWER_SNAPSHOT)
    detail = _render_evidence_detail_mfd(cards, selected_index=_power_index(cards))
    listing = _render_evidence_list_mfd(cards, selected_index=_power_index(cards))

    assert "выбрано:" in detail
    assert "ПИТАНИЕ/НАКОПИТЕЛИ" in detail
    assert "SoC_bat: 42%" in detail
    assert "SoC_cap: 79%" in detail
    assert "PDU_boundary: target-only; no full PDU runtime in this patch" in detail
    assert "PDU_allowance" not in detail
    assert "BODY_MODULE_ATTACH_REGISTERED" not in detail
    assert ">" in listing
    assert ">" + f"{_power_index(cards) + 1:02d}. ПИТАНИЕ/НАКОПИТЕЛИ" in listing


def test_f8_detail_uses_unknown_for_missing_power_telemetry_terms() -> None:
    cards = build_evidence_card_vms({})
    detail = _render_evidence_detail_mfd(cards, selected_index=_power_index(cards))

    assert "ПИТАНИЕ/НАКОПИТЕЛИ" in detail
    assert "SoC_bat: unknown" in detail
    assert "SoC_cap: unknown" in detail
    assert "POWER_TELEM_MISSING" in detail
    assert "None%" not in detail
    assert "-%" not in detail
    assert "84%" not in detail
    assert "61%" not in detail
    assert "battery: SoC" not in detail
    assert "supercap: SoC" not in detail


class _Host(App):
    def __init__(self, snapshot, *, preferred_card_type: str | None = None) -> None:
        self._snapshot = snapshot
        self._preferred_card_type = preferred_card_type
        super().__init__()

    def compose(self) -> ComposeResult:
        yield OrionVEvidenceScreen(
            self._snapshot,
            preferred_card_type=self._preferred_card_type,
        )


@pytest.mark.asyncio
async def test_f8_screen_prefers_power_detail_when_opened_from_power_context() -> None:
    app = _Host(_POWER_SNAPSHOT, preferred_card_type="ПИТАНИЕ/НАКОПИТЕЛИ")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        screen = app.query_one(OrionVEvidenceScreen)

        assert screen.selected_evidence_subsystem == "ПИТАНИЕ/НАКОПИТЕЛИ"
        right_text = str(app.query_one("#orionv-evidence-mfd-right-screen").render())
        assert "ПИТАНИЕ/НАКОПИТЕЛИ" in right_text
        assert "SoC_bat: 42%" in right_text
        assert "BODY_MODULE_ATTACH_REGISTERED" not in right_text


@pytest.mark.asyncio
async def test_f8_screen_keyboard_selection_changes_detail_card_read_only() -> None:
    app = _Host(_POWER_SNAPSHOT)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        screen = app.query_one(OrionVEvidenceScreen)
        assert screen.selected_evidence_index == 0
        first_subsystem = screen.selected_evidence_subsystem

        screen.select_next_evidence_card()
        await pilot.pause()
        assert screen.selected_evidence_index == 1
        assert screen.selected_evidence_subsystem != first_subsystem

        screen.select_previous_evidence_card()
        await pilot.pause()
        assert screen.selected_evidence_index == 0
        assert screen.selected_evidence_subsystem == first_subsystem

        right_text = str(app.query_one("#orionv-evidence-mfd-right-screen").render())
        assert "панель улик не исполняет команды" in right_text
