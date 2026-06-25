"""ORION V evidence-card stream panel (route a, IF-NBL-001 step 1c).

A read-only vertical stream of evidence cards built from ONE telemetry snapshot via the
console-side adapters and the canon ``*_evidence`` projections — never from the legacy
contour and never by extending collector.build_*. v1 shows the NBL card; more slices
append here. Follows the existing ORION V idiom: a ``Static`` level-panel (not a Textual
Screen), shown/hidden by the app.
"""
from __future__ import annotations

from typing import Any, Mapping

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from qiki.services.operator_console.orion_v.evidence_adapters import snapshot_to_nbl_record
from qiki.services.operator_console.orion_v.evidence_card_vm import nbl_evidence_to_card_vm
from qiki.services.operator_console.orion_v.nbl_evidence import nbl_to_evidence
from qiki.services.operator_console.orion_v.widgets.evidence_card_view import OrionVEvidenceCard


def build_evidence_cards(snapshot: Mapping[str, Any]) -> list[OrionVEvidenceCard]:
    """Build the read-only evidence cards for one telemetry snapshot (route a).

    v1: a single NBL card. Each card is honest by construction — its content comes from
    the ``*_evidence`` projection; nothing is invented in the view layer.
    """
    snapshot = snapshot or {}
    vms = [
        nbl_evidence_to_card_vm(nbl_to_evidence(snapshot_to_nbl_record(snapshot))),
    ]
    return [OrionVEvidenceCard(vm) for vm in vms]


class OrionVEvidenceScreen(Static):
    """Read-only evidence-card stream level-panel for ORION V."""

    DEFAULT_CSS = """
    OrionVEvidenceScreen { height: 1fr; layout: vertical; }
    OrionVEvidenceScreen #orionv-evidence-title {
        height: auto; color: $text-muted; padding: 0 1;
    }
    OrionVEvidenceScreen #orionv-evidence-stream { height: 1fr; }
    """

    def __init__(self, snapshot: Mapping[str, Any] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._snapshot = snapshot or {}

    def compose(self) -> ComposeResult:
        yield Static("ORION · EVIDENCE (read-only)", id="orionv-evidence-title")
        with VerticalScroll(id="orionv-evidence-stream"):
            for card in build_evidence_cards(self._snapshot):
                yield card

    def update_snapshot(self, snapshot: Mapping[str, Any]) -> None:
        """Rebuild the stream from a fresh snapshot (stable IDs / point-update come later)."""
        self._snapshot = snapshot or {}
        stream = self.query_one("#orionv-evidence-stream", VerticalScroll)
        stream.remove_children()
        stream.mount(*build_evidence_cards(self._snapshot))
