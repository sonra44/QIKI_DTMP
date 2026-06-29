"""Textual dashboard composition for ORION V Power / Accumulator / Thermal.

This dashboard makes SoC_bat, SoC_cap, PDU boundary, peak readiness and thermal
nodes visible without implementing a full PDU or thermal simulation.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    PowerThermalConsoleViewModel,
    get_power_thermal_console_view_model,
)
from qiki.services.operator_console.orion_v.widgets.power_status_bar import PowerStatusBar
from qiki.services.operator_console.orion_v.widgets.power_thermal_panel import PowerThermalPanel
from qiki.services.operator_console.orion_v.widgets.thermal_node_table import ThermalNodeTable


class PowerThermalTextualDashboard(Vertical):
    """Power / Accumulator / Thermal dashboard using real Textual widgets."""

    DEFAULT_CSS = """
    PowerThermalTextualDashboard {
        height: auto;
        min-height: 20;
        border: round $surface-lighten-1 30%;
        padding: 0 1;
    }
    PowerThermalTextualDashboard #power-thermal-columns {
        height: auto;
        layout: horizontal;
    }
    """

    def __init__(self, vm: PowerThermalConsoleViewModel | None = None, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._vm = vm or get_power_thermal_console_view_model()

    def compose(self) -> ComposeResult:
        yield Static("ORION V / POWER · ACCUMULATOR · THERMAL SEED", id="orionv-power-thermal-title")
        yield PowerStatusBar(self._vm, id="orionv-power-status-bar")
        with Horizontal(id="power-thermal-columns"):
            yield PowerThermalPanel(self._vm, id="orionv-power-thermal-panel")
            yield ThermalNodeTable(self._vm, id="orionv-thermal-node-table")
        yield Static(
            "Truth: SoC_bat is reserve; SoC_cap is supercap peak readiness; "
            "source=local_power_thermal_seed_fixture; runtime conformance not claimed",
            id="orionv-power-thermal-trust-note",
        )

    def update_view_model(self, vm: PowerThermalConsoleViewModel | None = None) -> None:
        self._vm = vm or get_power_thermal_console_view_model()
        try:
            self.query_one("#orionv-power-status-bar", PowerStatusBar).update_view_model(self._vm)
            self.query_one("#orionv-power-thermal-panel", PowerThermalPanel).update_view_model(self._vm)
            self.query_one("#orionv-thermal-node-table", ThermalNodeTable).update_view_model(self._vm)
        except Exception:
            # During early compose/mount order in tests, widgets may not yet exist. The
            # next on_mount/refresh will rebuild from self._vm.
            return
