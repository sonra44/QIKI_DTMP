"""Textual detail panel for ORION V Power / Accumulator / Thermal."""

from __future__ import annotations

from textual.widgets import Static

from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    PowerThermalConsoleViewModel,
    format_power_accumulator_mfd_lines,
)


class PowerThermalPanel(Static):
    """Read-only power/accumulator/thermal detail panel."""

    DEFAULT_CSS = """
    PowerThermalPanel {
        height: auto;
        min-height: 16;
        padding: 0 1;
        border: round $surface-lighten-1 30%;
    }
    """

    def __init__(self, vm: PowerThermalConsoleViewModel, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._vm = vm

    def on_mount(self) -> None:
        self.update_view_model(self._vm)

    def update_view_model(self, vm: PowerThermalConsoleViewModel) -> None:
        self._vm = vm
        self.update("\n".join(format_power_accumulator_mfd_lines(vm)))
