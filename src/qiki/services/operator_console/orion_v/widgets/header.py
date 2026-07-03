from __future__ import annotations

from textual.widgets import Static

from qiki.services.operator_console.orion_v.i18n_ru import tr
from qiki.services.operator_console.orion_v.operator_state import OperatorShellState


class OrionVHeader(Static):
    """Compact mission strip for the canonical ORION V shell."""

    def __init__(self, **kwargs):
        super().__init__("ORION V | Mission Control", **kwargs)
        self._state = OperatorShellState.empty()

    def set_state(self, state: OperatorShellState) -> None:
        self._state = state
        self._refresh_text()

    def _refresh_text(self) -> None:
        always_on = self._state.always_on
        derived = self._state.derived
        link_status = str(always_on.link_status or "unknown").strip().lower()
        mapping = {
            "connected": tr("online"),
            "up": tr("online"),
            "replay": "replay",
            "degraded": tr("reconnecting"),
            "reconnecting": tr("reconnecting"),
            "offline": tr("offline"),
            "lost": tr("offline"),
        }
        color_map = {
            "connected": "green",
            "up": "green",
            "replay": "cyan",
            "degraded": "yellow",
            "reconnecting": "yellow",
            "offline": "red",
            "lost": "red",
        }
        status = mapping.get(link_status, link_status or "unknown")
        status_color = color_map.get(link_status, "white")
        freshness_seconds = (
            always_on.telemetry_age_ms / 1000.0
            if isinstance(always_on.telemetry_age_ms, (int, float))
            else None
        )
        # MISSION_CONTROL_STRIP_CANON / ADR-0016: the primary row shows the DATA
        # freshness CODE (OK/LAG/STALE/NODATA); the exact age goes to the tooltip.
        # Closes F-4b: no more "СВЕЖ unknown" while telemetry is actually flowing.
        freshness = derived.data_freshness_state or "NODATA"
        age_hint = f"{freshness_seconds:.1f}s" if freshness_seconds is not None else "нет данных"
        latency = (
            f"{always_on.signal_latency_ms:.0f}ms"
            if isinstance(always_on.signal_latency_ms, (int, float))
            else "n/a"
        )
        loss = (
            f"{always_on.packet_loss_percent:.1f}%"
            if isinstance(always_on.packet_loss_percent, (int, float))
            else "n/a"
        )
        mode_value = str(always_on.vehicle_mode or "").strip()
        if not mode_value or mode_value.lower() in {"n/a", "unknown", "нет данных", "none"}:
            mode_value = "—"
        authority_value = str(always_on.control_authority or "").strip() or "operator"

        line_1 = (
            "[b]ORION V[/b]  [dim]операторский контур[/dim]"
            f" | L: [b]{self._state.level_label}[/b]"
            f" | P: [b]{always_on.mission_phase or 'unknown'}[/b]"
            f" | M: [b]{mode_value}[/b]"
            f" | A: [b]{authority_value}[/b]"
        )
        # avoid "СВЯЗЬ Связь отсутствует": the status value may already start with the word
        status_text = status[6:].lstrip() if status.lower().startswith("связь ") else status
        line_2 = (
            f"СВЯЗЬ [{status_color}]{status_text}[/{status_color}]"
            f" | СВЕЖ [b]{freshness}[/b]"
            f" | ЗАДЕРЖ [b]{latency}[/b]"
            f" | ПОТЕРИ [b]{loss}[/b]"
            f" | СОБЫТ [b]{self._state.events_count}[/b]"
        )
        if always_on.last_contact_timestamp:
            line_2 += f" | RX [b]{always_on.last_contact_timestamp}[/b]"
        # canon: human detail (exact age) lives in the tooltip, not the primary row
        self.tooltip = f"СВЕЖ/DATA: возраст {age_hint} | ЗАДЕРЖ {latency} | ПОТЕРИ {loss}"
        self.update("\n".join((line_1, line_2)))
