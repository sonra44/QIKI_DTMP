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
from qiki.shared.body_status import (
    POWER_BUS_CRIT_V,
    POWER_BUS_WARN_V,
    POWER_SOC_CRIT_PCT,
    POWER_SOC_WARN_PCT,
)


NO_DATA_REASON = "degraded: нет данных"
BOOL_YES = "да"
BOOL_NO = "нет"


class PowerSubsystemModule(SubsystemModule):
    """Power subsystem panel using real telemetry fields."""

    slug = "power"
    title = "Энергия"

    @staticmethod
    def _power_payload(telemetry: dict[str, Any]) -> dict[str, Any]:
        power = telemetry.get("power")
        if isinstance(power, dict):
            return power
        return {}

    @staticmethod
    def _format_load_shedding(value: Any) -> str:
        if isinstance(value, bool):
            return BOOL_YES if value else BOOL_NO
        if isinstance(value, dict):
            if "state" in value:
                return str(value.get("state") or "—")
            if "active" in value:
                active = value.get("active")
                if isinstance(active, bool):
                    return BOOL_YES if active else BOOL_NO
        if value is None:
            return "—"
        text = str(value).strip()
        return text or "—"

    @staticmethod
    def _extract_shed_reasons(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            return [part for part in parts if part]
        return []

    def render_summary(self, state: dict[str, Any]) -> str:
        telemetry = telemetry_from_state(state)
        power = self._power_payload(telemetry)
        soc = pick_num(telemetry, ["power", "soc_pct"])
        if soc is None:
            soc = pick_num(telemetry, ["battery", "soc_pct"])
        if soc is None:
            soc = pick_num(telemetry, ["battery"])
        bus_v = pick_num(telemetry, ["power", "bus_v"])
        limit_mode = pick_text(telemetry, ["power", "limit_mode"])
        warning = pick_text(telemetry, ["power", "warning"]).lower()

        # Аудит 0.17: пороги — ТОЛЬКО shared-канон (были локальные 30%/24В
        # против канона 20%/22В — карточка F2 противоречила чипам F1).
        crit = (
            (soc is not None and soc <= POWER_SOC_CRIT_PCT)
            or (bus_v is not None and bus_v < POWER_BUS_CRIT_V)
            or "crit" in warning
        )
        warn = (
            (soc is not None and soc <= POWER_SOC_WARN_PCT)
            or (bus_v is not None and bus_v < POWER_BUS_WARN_V)
            or ("warn" in warning)
            or ("alarm" in warning)
        )
        ok = soc is not None or bus_v is not None
        status = status_tag(ok=ok, warn=warn, crit=crit)

        soc_text = f"{tr('soc')} {soc:.1f}%" if soc is not None else f"{tr('soc')} {NO_DATA_REASON}"
        bus_text = f"{tr('bus_voltage')} {bus_v:.1f}V" if bus_v is not None else f"{tr('bus_voltage')} —"
        mode_text = f"{tr('limit_mode')} {limit_mode}" if limit_mode else f"{tr('limit_mode')} —"
        reasons = self._extract_shed_reasons(power.get("shed_reasons"))
        reasons_text = (
            f"{tr('shed_reasons')} {', '.join(reasons)}"
            if reasons
            else f"{tr('shed_reasons')} {'—'}"
        )
        return f"{status} | {soc_text} | {bus_text} | {mode_text} | {reasons_text}"

    def render_details(self, state: dict[str, Any]) -> str:
        telemetry = telemetry_from_state(state)
        power = self._power_payload(telemetry)
        bus_v = pick_num(telemetry, ["power", "bus_v"])
        bus_a = pick_num(telemetry, ["power", "bus_a"])
        limit_mode = pick_text(telemetry, ["power", "limit_mode"])
        shedding = self._format_load_shedding(power.get("load_shedding"))
        reasons = self._extract_shed_reasons(power.get("shed_reasons"))
        reasons_text = ", ".join(reasons) if reasons else NO_DATA_REASON if shedding == BOOL_YES else "—"
        warning = pick_text(telemetry, ["power", "warning"])

        loads = telemetry.get("loads")
        if isinstance(loads, dict) and loads:
            active_loads = ", ".join(sorted(str(k) for k, v in loads.items() if bool(v))) or "—"
        else:
            active_loads = "—"

        lines = [
            f"{self.title}: детали",
            f"- {tr('bus_voltage')}: {f'{bus_v:.2f}V' if bus_v is not None else NO_DATA_REASON}",
            f"- {tr('bus_current')}: {f'{bus_a:.2f}A' if bus_a is not None else NO_DATA_REASON}",
            f"- {tr('limit_mode')}: {limit_mode or '—'}",
            f"- {tr('load_shedding')}: {shedding}",
            f"- {tr('shed_reasons')}: {reasons_text}",
            f"- Активные нагрузки: {active_loads}",
            f"- Предупреждение: {warning or '—'}",
            "",
            "Источники истины:",
        ]
        lines.extend(f"- {src}" for src in self.sources_of_truth())
        return "\n".join(lines)

    def sources_of_truth(self) -> tuple[str, ...]:
        return (
            "power.soc_pct",
            "power.bus_v",
            "power.bus_a",
            "power.limit_mode",
            "power.load_shedding",
            "power.shed_reasons",
            "loads.*",
        )
