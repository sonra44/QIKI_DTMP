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


class DockingSubsystemModule(SubsystemModule):
    slug = "docking"
    title = "Стыковка"

    def render_summary(self, state: dict[str, Any]) -> str:
        telemetry = telemetry_from_state(state)
        mode = pick_text(telemetry, ["docking", "state"]).lower()
        target = pick_text(telemetry, ["docking", "target_id"])
        distance = pick_num(telemetry, ["docking", "distance_m"])
        rel_speed = pick_num(telemetry, ["docking", "rel_speed_mps"])

        crit = mode in {"abort", "failed", "error"} or (
            distance is not None and rel_speed is not None and distance < 5.0 and rel_speed > 0.5
        )
        warn = mode in {"approach", "aligning"} or (
            distance is not None and rel_speed is not None and distance < 20.0 and rel_speed > 0.2
        )
        ok = mode in {"docked", "capture"} or target != "" or distance is not None
        status = status_tag(ok=ok, warn=warn, crit=crit)

        mode_text = f"Состояние стыковки {mode.upper()}" if mode else f"Состояние стыковки {NO_DATA_REASON}"
        target_text = f"Цель {target}" if target else "Цель —"
        dist_text = f"Дистанция {distance:.1f}м" if distance is not None else "Дистанция —"
        return f"{status} | {mode_text} | {target_text} | {dist_text}"

    def render_details(self, state: dict[str, Any]) -> str:
        telemetry = telemetry_from_state(state)
        mode = pick_text(telemetry, ["docking", "state"])
        target = pick_text(telemetry, ["docking", "target_id"])
        distance = pick_num(telemetry, ["docking", "distance_m"])
        rel_speed = pick_num(telemetry, ["docking", "rel_speed_mps"])
        align_err = pick_num(telemetry, ["docking", "alignment_error_deg"])
        warning = pick_text(telemetry, ["docking", "warning"])

        lines = [
            f"{self.title}: детали",
            f"- Состояние стыковки: {mode or NO_DATA_REASON}",
            f"- Цель: {target or NO_DATA_REASON}",
            f"- Дистанция: {f'{distance:.2f}м' if distance is not None else NO_DATA_REASON}",
            f"- Относительная скорость: {f'{rel_speed:.3f}м/с' if rel_speed is not None else NO_DATA_REASON}",
            f"- {tr('alignment_error')}: {f'{align_err:.2f}°' if align_err is not None else NO_DATA_REASON}",
            f"- Предупреждение: {warning or '—'}",
            "",
            "Источники истины:",
        ]
        lines.extend(f"- {src}" for src in self.sources_of_truth())
        return "\n".join(lines)

    def sources_of_truth(self) -> tuple[str, ...]:
        return (
            "docking.state",
            "docking.target_id",
            "docking.distance_m",
            "docking.rel_speed_mps",
            "docking.alignment_error_deg",
            "docking.warning",
        )
