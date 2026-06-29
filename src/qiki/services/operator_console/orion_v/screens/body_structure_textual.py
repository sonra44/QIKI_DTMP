"""Textual dashboard composition for ORION V Body Structure.

This module converts the existing body-structure view model into proper Textual
widgets: a status bar, Face Map DataTable, selected-face panel, evidence panel,
and action footer. It is not new runtime physics and does not bypass audit or
Evidence Card sources.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from qiki.services.operator_console.orion_v.body_structure_view_model import (
    BodyStructureConsoleViewModel,
    get_body_structure_console_view_model,
)
from qiki.services.operator_console.orion_v.widgets.body_evidence_panel import BodyEvidencePanel
from qiki.services.operator_console.orion_v.widgets.body_status_bar import BodyStatusBar
from qiki.services.operator_console.orion_v.widgets.face_map_table import FaceMapTable
from qiki.services.operator_console.orion_v.widgets.selected_face_panel import SelectedFacePanel


class BodyActionFooter(Static):
    """Operator hint strip for Textual body-structure actions."""

    DEFAULT_CSS = """
    BodyActionFooter {
        height: auto;
        padding: 0 1;
        border: round $surface-lighten-1 30%;
        color: $text-muted;
    }
    """

    def update_view_model(self, vm: BodyStructureConsoleViewModel) -> None:
        self.update(
            "B attach self-check | R reset | N next face | P previous face | "
            f"selected={vm.selected_face_id} | hint={vm.operator_hint}"
        )


class BodyStructureTextualDashboard(Vertical):
    """Textual widget dashboard for visible QIKI Body Structure telemetry."""

    DEFAULT_CSS = """
    BodyStructureTextualDashboard {
        height: auto;
        min-height: 26;
        border: round $surface-lighten-1 30%;
        padding: 0 1;
    }

    BodyStructureTextualDashboard #orionv-body-dashboard-title {
        height: auto;
        color: $text-muted;
        padding: 0 1;
    }

    BodyStructureTextualDashboard #orionv-body-main-row {
        height: auto;
    }
    """

    def __init__(self, vm: BodyStructureConsoleViewModel | None = None, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._vm = vm or get_body_structure_console_view_model()
        self._status_bar = BodyStatusBar(self._vm, id="orionv-body-status-bar")
        self._face_table = FaceMapTable(self._vm, id="orionv-body-face-map-table")
        self._selected_panel = SelectedFacePanel(self._vm, id="orionv-body-selected-face")
        self._evidence_panel = BodyEvidencePanel(self._vm, id="orionv-body-evidence-panel")
        self._footer = BodyActionFooter(id="orionv-body-action-footer")

    def compose(self) -> ComposeResult:
        yield Static("ORION V / BODY STRUCTURE", id="orionv-body-dashboard-title")
        yield self._status_bar
        with Horizontal(id="orionv-body-main-row"):
            yield self._face_table
            yield self._selected_panel
        yield self._evidence_panel
        yield self._footer

    def on_mount(self) -> None:
        self.update_view_model(self._vm)

    def refresh_from_controller(self) -> None:
        self.update_view_model(get_body_structure_console_view_model())

    def refresh_from_view_model(self, vm: BodyStructureConsoleViewModel) -> None:
        """Compatibility alias used by ORION F2 screen refresh code."""
        self.update_view_model(vm)

    def update_view_model(self, vm: BodyStructureConsoleViewModel) -> None:
        """Refresh all Textual child widgets from one read-only VM snapshot."""
        self._vm = vm
        self._status_bar.update_view_model(vm)
        self._face_table.update_view_model(vm)
        self._selected_panel.update_view_model(vm)
        self._evidence_panel.update_view_model(vm)
        self._footer.update_view_model(vm)


__all__ = ["BodyActionFooter", "BodyStructureTextualDashboard"]
