"""Textual status widget for ORION V Body Structure.

This widget renders a compact operator-facing status line from the existing
BodyStructureConsoleViewModel. It is a view layer only: it never mutates body
runtime state and never claims full QIKI Body runtime readiness.
"""

from __future__ import annotations

from textual.widgets import Static

from qiki.services.operator_console.orion_v.body_structure_view_model import (
    BodyStructureConsoleViewModel,
)


class BodyStatusBar(Static):
    """Compact Textual status strip for the body-structure dashboard."""

    DEFAULT_CSS = """
    BodyStatusBar {
        height: auto;
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
        decision = vm.last_decision
        if decision == "waiting":
            text = (
                f"QIKI BODY: {vm.seed_status} | faces={vm.faces_total} | "
                f"modules={vm.attached_modules_count} | selected={vm.selected_face_id} | "
                f"press B"
            )
        elif vm.interaction_state == "already_attached":
            text = (
                f"QIKI BODY: online | faces={vm.faces_total} | "
                f"modules={vm.attached_modules_count} | selected={vm.selected_face_id} | "
                "already attached; press R"
            )
        else:
            text = (
                f"QIKI BODY: {vm.seed_status} | faces={vm.faces_total} | "
                f"modules={vm.attached_modules_count} | selected={vm.selected_face_id} | "
                f"{vm.mount_point}=occupied | evidence={vm.trust_status}"
            )
        self.update(text)
