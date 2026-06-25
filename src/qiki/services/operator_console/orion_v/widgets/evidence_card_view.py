"""One read-only ORION evidence card widget (route a, IF-NBL-001 step 1b).

Decision-first: a left accent bar carries severity, the first line is glyph + subsystem
+ headline, with reason and detail below. The widget is a thin presenter — all honesty
markers come from the EvidenceCardVM; nothing is computed or invented here. Built only
from the Textual built-in ``Static`` (no plugins / no extra pip deps).
"""
from __future__ import annotations

from textual.widgets import Static

from qiki.services.operator_console.orion_v.evidence_card_vm import (
    EvidenceCardVM,
    render_card_text,
)


class OrionVEvidenceCard(Static):
    """A single focusable evidence card. Accent bar reflects ``vm.state_key``."""

    can_focus = True

    DEFAULT_CSS = """
    OrionVEvidenceCard {
        height: auto;
        padding: 0 1;
        margin: 0 0 1 0;
        border-left: thick $surface-lighten-2;
    }
    OrionVEvidenceCard:focus { background: $boost; }
    OrionVEvidenceCard.state-ok       { border-left: thick $success; }
    OrionVEvidenceCard.state-degraded { border-left: thick $warning; }
    OrionVEvidenceCard.state-blocked  { border-left: thick $error; }
    OrionVEvidenceCard.state-missing  { border-left: thick $surface-lighten-2; }
    OrionVEvidenceCard.state-target   { border-left: thick $accent; }
    """

    def __init__(self, vm: EvidenceCardVM, **kwargs) -> None:
        super().__init__(**kwargs)
        self._vm = vm

    def on_mount(self) -> None:
        self.set_class(True, f"state-{self._vm.state_key}")
        self.update(render_card_text(self._vm))
