from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

__all__ = ["OrionVActionBar", "OrionVAlertsOverlay", "OrionVHeader", "OrionVStatusBars"]

if TYPE_CHECKING:
    from qiki.services.operator_console.orion_v.widgets.action_bar import OrionVActionBar
    from qiki.services.operator_console.orion_v.widgets.alerts_overlay import OrionVAlertsOverlay
    from qiki.services.operator_console.orion_v.widgets.header import OrionVHeader
    from qiki.services.operator_console.orion_v.widgets.status_bars import OrionVStatusBars


def __getattr__(name: str) -> object:
    module_by_name = {
        "OrionVActionBar": "action_bar",
        "OrionVAlertsOverlay": "alerts_overlay",
        "OrionVHeader": "header",
        "OrionVStatusBars": "status_bars",
    }
    if name not in module_by_name:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.{module_by_name[name]}")
    return getattr(module, name)
