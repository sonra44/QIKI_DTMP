"""IF-NBL-001 step 1c: Textual mount-smoke for the evidence-card stream panel.

Mounts OrionVEvidenceScreen in a real Textual app (Pilot) and proves the CSS parses and
the NBL card actually renders with its honest accent + content — the runtime check the
pure VM/render tests could not give. Uses a fixture snapshot purely to validate the
visual; the live card with real q-sim data appears when wired into ORION V.
"""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from qiki.services.operator_console.orion_v.screens.evidence_stream import OrionVEvidenceScreen
from qiki.services.operator_console.orion_v.widgets.evidence_card_view import OrionVEvidenceCard


class _Host(App):
    def __init__(self, snapshot) -> None:
        self._snapshot = snapshot
        super().__init__()

    def compose(self) -> ComposeResult:
        yield OrionVEvidenceScreen(self._snapshot)


def _rendered_nbl_cards(cards) -> list[tuple[OrionVEvidenceCard, str]]:
    rendered: list[tuple[OrionVEvidenceCard, str]] = []
    for card in cards:
        text = str(card.render())
        if "NBL_NOT_IMPLEMENTED" in text:
            rendered.append((card, text))
    return rendered


@pytest.mark.asyncio
async def test_evidence_screen_mounts_and_renders_nbl_card() -> None:
    app = _Host({"power": {"nbl_active": True, "nbl_allowed": False, "nbl_budget_w": 0.0}})
    async with app.run_test(size=(90, 22)) as pilot:
        await pilot.pause()
        cards = app.query(OrionVEvidenceCard)
        nbl_cards = _rendered_nbl_cards(cards)
        assert len(nbl_cards) == 1                  # one NBL card mounted among F8 cards
        card, text = nbl_cards[0]
        assert card.has_class("state-target")       # CSS parsed; target-only accent applied
        assert "NBL_NOT_IMPLEMENTED" in text
        assert "NBL_RULES_ONLY" in text
        assert "NBL_PDU_DENIED" in text             # nbl_allowed False -> power-denied reason
        visible_list = str(app.query_one("#orionv-evidence-mfd-left-screen", Static).render())
        assert "NBL_NOT_IMPLEMENTED" in visible_list
        assert "NBL_PDU_DENIED" in visible_list


@pytest.mark.asyncio
async def test_screen_update_snapshot_rebuilds_single_card() -> None:
    app = _Host({})                                 # empty: no power-denied reason yet
    async with app.run_test(size=(90, 22)) as pilot:
        await pilot.pause()
        assert "NBL_PDU_DENIED" not in str(app.query_one(OrionVEvidenceCard).render())
        app.query_one(OrionVEvidenceScreen).update_snapshot(
            {"power": {"nbl_active": True, "nbl_allowed": False, "nbl_budget_w": 0.0}}
        )
        await pilot.pause()
        cards = app.query(OrionVEvidenceCard)
        nbl_cards = _rendered_nbl_cards(cards)
        assert len(nbl_cards) == 1                   # one NBL card after rebuild (no leak)
        assert "NBL_PDU_DENIED" in nbl_cards[0][1]   # new reason now present
        visible_list = str(app.query_one("#orionv-evidence-mfd-left-screen", Static).render())
        assert "NBL_PDU_DENIED" in visible_list
