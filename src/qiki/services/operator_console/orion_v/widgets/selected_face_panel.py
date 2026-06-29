"""Textual selected-face detail panel for ORION V Body Structure."""

from __future__ import annotations

from textual.widgets import Static

from qiki.services.operator_console.orion_v.body_structure_view_model import (
    BodyStructureConsoleViewModel,
)


class SelectedFacePanel(Static):
    """Selected Face panel for F2 Body Structure dashboard."""

    DEFAULT_CSS = """
    SelectedFacePanel {
        height: 16;
        min-width: 40;
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
        self.update(
            "Selected Face\n"
            f"face_id: {vm.selected_face_id}\n"
            f"role: {vm.selected_face_role}\n"
            f"occupancy: {vm.selected_face_occupancy}\n"
            f"module: {vm.selected_face_module_id or 'none'}\n"
            f"passport: {vm.passport_status}\n"
            f"runtime_ready: {str(vm.runtime_ready).lower()}\n"
            f"capability: {vm.capability_status}\n"
            "\nLast Action\n"
            f"action: {vm.last_action}\n"
            f"decision: {vm.last_decision}\n"
            f"before: modules={vm.before_modules_count}, F06={vm.before_mount_state}\n"
            f"after: modules={vm.after_modules_count}, F06={vm.after_mount_state}"
        )
