"""Textual evidence panel for ORION V Body Structure."""

from __future__ import annotations

from textual.widgets import Static

from qiki.services.operator_console.orion_v.body_structure_view_model import (
    BodyStructureConsoleViewModel,
)


class BodyEvidencePanel(Static):
    """Read-only evidence panel for the body-structure dashboard."""

    DEFAULT_CSS = """
    BodyEvidencePanel {
        height: auto;
        min-height: 5;
        padding: 0 1;
        border: round $surface-lighten-1 30%;
    }
    """

    def __init__(self, vm: BodyStructureConsoleViewModel, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._vm = vm

    def on_mount(self) -> None:
        self.update_view_model(self._vm)

    def update_view_model(self, vm: BodyStructureConsoleViewModel) -> None:
        self._vm = vm
        if vm.evidence_card is None:
            text = (
                "Evidence\n"
                "BODY STRUCTURE EVIDENCE: no attach card yet.\n"
                "Press B to run the local attach self-check.\n"
                "read_only: true"
            )
        else:
            text = (
                "Evidence\n"
                f"{vm.evidence_card_type} | {vm.trust_status} | read_only={str(vm.read_only).lower()}\n"
                f"module: {vm.module_id}\n"
                f"face: {vm.mount_point}\n"
                f"audit={vm.audit_event_id}\n"
                f"audit_event_id: {vm.audit_event_id}\n"
                f"card={vm.evidence_card_id}\n"
                f"evidence_card_id: {vm.evidence_card_id}"
            )
        self.update(text)
