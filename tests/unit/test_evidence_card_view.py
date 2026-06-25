"""IF-NBL-001 step 1b: evidence-card view-model + renderer (honesty-bound, no plugins).

Pure tests (no Textual import) over the real chain
snapshot -> adapter -> nbl_to_evidence -> card view-model -> rendered text.
The widget itself is a thin Static presenter of render_card_text(); its visual form is
verified later when wired into ORION V (step 1c).
"""
from __future__ import annotations

from qiki.services.operator_console.orion_v.evidence_adapters import snapshot_to_nbl_record
from qiki.services.operator_console.orion_v.evidence_card_vm import (
    STATE_STYLE,
    nbl_evidence_to_card_vm,
    render_card_text,
)
from qiki.services.operator_console.orion_v.nbl_evidence import nbl_to_evidence


def _vm(snapshot):
    return nbl_evidence_to_card_vm(nbl_to_evidence(snapshot_to_nbl_record(snapshot)))


def test_nbl_card_is_target_only_never_sent() -> None:
    # Even an allowed/active power state must not turn the card "ok"/sent.
    vm = _vm({"power": {"nbl_active": True, "nbl_allowed": True, "nbl_budget_w": 20.0}})
    assert vm.state_key == "target"            # §17.10 target-only, never "ok"
    assert "target-only" in vm.headline
    assert "NBL_NOT_IMPLEMENTED" in vm.reason_text
    assert "NBL_RULES_ONLY" in vm.reason_text


def test_missing_fields_shown_as_no_data_not_faked() -> None:
    joined = " | ".join(_vm({}).detail_lines)
    assert "нет данных" in joined              # missing -> honest "нет данных"
    assert "неизвестно" in joined              # delivery unknown -> "неизвестно"


def test_render_uses_safe_glyphs_and_no_ambiguous_circle() -> None:
    text = render_card_text(_vm({"power": {"nbl_allowed": False, "nbl_budget_w": 0.0}}))
    assert "◌ NBL" in text                     # 1-cell-safe target glyph
    assert "●" not in text                # '●' Ambiguous-width must never appear
    assert "причина:" in text
    assert "NBL_PDU_DENIED" in text            # honest power-denied reason surfaced


def test_state_style_glyphs_are_single_cell_safe() -> None:
    glyphs = {g for g, _ in STATE_STYLE.values()}
    assert "●" not in glyphs              # no ambiguous-width '●'
    assert glyphs <= {"✓", "⚠", "✗", "◌"}
