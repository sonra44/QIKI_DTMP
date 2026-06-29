"""Textual panel for the ORION V body-physics pending seed."""

from __future__ import annotations

from textual.widgets import Static

from qiki.services.operator_console.orion_v.body_physics_view_model import (
    BodyPhysicsConsoleViewModel,
    format_body_physics_system_summary,
)


class BodyPhysicsPanel(Static):
    """Read-only panel that surfaces pending mass / CoM / inertia consequences."""

    DEFAULT_CSS = """
    BodyPhysicsPanel {
        height: auto;
        min-height: 12;
        padding: 0 1;
        border: round $surface-lighten-1 30%;
    }
    """

    def __init__(self, vm: BodyPhysicsConsoleViewModel, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._vm = vm

    def on_mount(self) -> None:
        self.update_view_model(self._vm)

    def update_view_model(self, vm: BodyPhysicsConsoleViewModel) -> None:
        self._vm = vm
        self.update(format_body_physics_system_summary(vm))
