"""Textual status widget for ORION V Power / Thermal."""

from __future__ import annotations

from textual.widgets import Static

from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    PowerThermalConsoleViewModel,
    format_power_thermal_cockpit_line,
)


class PowerStatusBar(Static):
    """Compact Textual status strip for the power/thermal dashboard."""

    DEFAULT_CSS = """
    PowerStatusBar {
        height: auto;
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
        self.update(format_power_thermal_cockpit_line(vm))
