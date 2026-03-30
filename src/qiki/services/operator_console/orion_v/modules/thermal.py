from __future__ import annotations

from typing import Any

from qiki.services.operator_console.orion_v.modules.base import SubsystemModule
from qiki.services.operator_console.orion_v.modules.common import (
    pick_num,
    pick_text,
    status_tag,
    telemetry_from_state,
)
from qiki.services.operator_console.orion_v.i18n_ru import tr


NO_DATA_REASON = "degraded: нет данных"


class ThermalSubsystemModule(SubsystemModule):
    slug = "thermal"
    title = "Терморежим"

    def render_summary(self, state: dict[str, Any]) -> str:
        telemetry = telemetry_from_state(state)
        core_c = pick_num(telemetry, ["thermal", "core_c"])
        if core_c is None:
            core_c = pick_num(telemetry, ["temp_core_c"])
        radiator_c = pick_num(telemetry, ["thermal", "radiator_c"])
        mode = pick_text(telemetry, ["thermal", "mode"])
        warning = pick_text(telemetry, ["thermal", "warning"]).lower()

        crit = (core_c is not None and core_c >= 90.0) or "crit" in warning or "trip" in warning
        warn = (core_c is not None and core_c >= 75.0) or "warn" in warning or "alarm" in warning
        ok = core_c is not None or radiator_c is not None
        status = status_tag(ok=ok, warn=warn, crit=crit)

        core_text = f"{tr('core_temp')} {core_c:.1f}C" if core_c is not None else f"{tr('core_temp')} {NO_DATA_REASON}"
        rad_text = f"{tr('radiator_temp')} {radiator_c:.1f}C" if radiator_c is not None else f"{tr('radiator_temp')} —"
        mode_text = f"Режим {mode}" if mode else "Режим —"
        return f"{status} | {core_text} | {rad_text} | {mode_text}"

    def render_details(self, state: dict[str, Any]) -> str:
        telemetry = telemetry_from_state(state)
        core_c = pick_num(telemetry, ["thermal", "core_c"])
        if core_c is None:
            core_c = pick_num(telemetry, ["temp_core_c"])
        radiator_c = pick_num(telemetry, ["thermal", "radiator_c"])
        sink_c = pick_num(telemetry, ["thermal", "sink_c"])
        mode = pick_text(telemetry, ["thermal", "mode"])
        warning = pick_text(telemetry, ["thermal", "warning"])
        trip = pick_text(telemetry, ["thermal", "trip_reason"])

        lines = [
            f"{self.title}: детали",
            f"- {tr('core_temp')}: {f'{core_c:.2f}C' if core_c is not None else NO_DATA_REASON}",
            f"- {tr('radiator_temp')}: {f'{radiator_c:.2f}C' if radiator_c is not None else NO_DATA_REASON}",
            f"- {tr('sink_temp')}: {f'{sink_c:.2f}C' if sink_c is not None else NO_DATA_REASON}",
            f"- Режим: {mode or '—'}",
            f"- Предупреждение: {warning or '—'}",
            f"- Причина аварийного отключения: {trip or '—'}",
            "",
            "Источники истины:",
        ]
        lines.extend(f"- {src}" for src in self.sources_of_truth())
        return "\n".join(lines)

    def sources_of_truth(self) -> tuple[str, ...]:
        return (
            "thermal.core_c",
            "temp_core_c",
            "thermal.radiator_c",
            "thermal.sink_c",
            "thermal.mode",
            "thermal.warning",
            "thermal.trip_reason",
        )
