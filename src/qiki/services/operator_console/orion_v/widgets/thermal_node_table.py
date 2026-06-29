"""Textual DataTable renderer for QIKI thermal nodes."""

from __future__ import annotations

from textual.widgets import DataTable

from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    PowerThermalConsoleViewModel,
    ThermalNodeView,
)


class ThermalNodeTable(DataTable):
    """Thermal node table widget backed by Textual DataTable."""

    DEFAULT_CSS = """
    ThermalNodeTable {
        height: 10;
        min-width: 44;
        border: round $surface-lighten-1 30%;
    }
    """

    def __init__(self, vm: PowerThermalConsoleViewModel, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._vm = vm
        self._columns_added = False

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.update_view_model(self._vm)

    def update_view_model(self, vm: PowerThermalConsoleViewModel) -> None:
        self._vm = vm
        if not self._columns_added:
            self.add_columns("node", "class", "temp", "blocked")
            self._columns_added = True
        self.clear()
        for node in vm.thermal_nodes:
            self.add_row(*_row_values(node), key=node.node_id)


def _row_values(node: ThermalNodeView) -> tuple[str, str, str, str]:
    temp = "unknown" if node.temperature_c is None else f"{node.temperature_c:.0f}C"
    blocked = ", ".join(node.blocked_commands) if node.blocked_commands else "-"
    return (node.node_id, node.thermal_class, temp, blocked)
