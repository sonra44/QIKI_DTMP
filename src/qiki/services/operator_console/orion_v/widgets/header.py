from __future__ import annotations

from textual.widgets import Static

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
        # MISSION_CONTROL_STRIP_CANON / ADR-0016 slice 4: the primary row carries
        # ONLY engineering codes (colour = severity); human wording and absorbed
        # detail (speed, latency/loss, age, raw states, events) live in the tooltip.
        always_on = self._state.always_on
        derived = self._state.derived

        # WORLD/МИР — truth-source #30 (always_on.world_run_state)
        world = always_on.world_run_state or "WAIT"
        world_color = {
            "RUN": "green",
            "PAUSE": "yellow",
            "STOP": "red",
            "REPLAY": "cyan",
            "WAIT": "yellow",
        }.get(world, "yellow")

        # LINK/СВЯЗЬ — absorbs latency/loss (detail → tooltip); no-data → LOST (red)
        link_raw = str(always_on.link_status or "").strip().lower()
        link = {
            "connected": "OK",
            "up": "OK",
            "replay": "REPLAY",
            "degraded": "WARN",
            "reconnecting": "WARN",
            "offline": "LOST",
            "lost": "LOST",
        }.get(link_raw, "LOST")
        link_color = {"OK": "green", "REPLAY": "cyan", "WARN": "yellow", "LOST": "red"}[link]

        # DATA/АКТУАЛ — freshness code (slice 3); exact age → tooltip
        data = derived.data_freshness_state or "NODATA"
        data_color = {"OK": "green", "LAG": "yellow", "STALE": "red", "NODATA": "yellow"}.get(data, "yellow")

        # SENS/СЕНС — collapse of the sensor-trust model states (#30); the strip
        # follows the model severity, exact state → tooltip/F3
        sens_raw = str(derived.sensor_trust_state or "").strip().lower()
        sens = {
            "trusted": "OK",
            "degraded": "WARN",
            "conflicting": "WARN",
            "blind": "WARN",
            "lottery": "FAIL",
        }.get(sens_raw, "WARN")
        sens_color = {"OK": "green", "WARN": "yellow", "FAIL": "red"}[sens]

        # CTRL/УПР — action gate; shown ONLY when authority != operator
        authority_raw = str(always_on.control_authority or "operator").strip().lower()
        ctrl: str | None = None
        ctrl_color = "cyan"
        if authority_raw != "operator":
            if authority_raw == "operator-confirm":
                ctrl, ctrl_color = "CONFIRM", "cyan"
            elif authority_raw == "analysis":
                ctrl, ctrl_color = "HOLD", "cyan"
            elif authority_raw.startswith("qiki"):
                ctrl, ctrl_color = "QIKI", ("green" if authority_raw == "qiki-allowed" else "red")
            else:  # safe-mode / q-core authority strings
                ctrl, ctrl_color = "SAFE", "red"

        line_1 = f"[b]ORION V[/b] | [b]{self._state.level_label}[/b]"
        parts = [
            f"МИР [{world_color}]{world}[/{world_color}]",
            f"СВЯЗЬ [{link_color}]{link}[/{link_color}]",
            f"АКТУАЛ [{data_color}]{data}[/{data_color}]",
            f"СЕНС [{sens_color}]{sens}[/{sens_color}]",
        ]
        if ctrl:
            parts.append(f"УПР [{ctrl_color}]{ctrl}[/{ctrl_color}]")
        line_2 = " | ".join(parts)

        # human wording + absorbed detail → tooltip (canon), click parity F7/F3/F6
        age_seconds = (
            always_on.telemetry_age_ms / 1000.0
            if isinstance(always_on.telemetry_age_ms, (int, float))
            else None
        )
        age_hint = f"{age_seconds:.1f}s" if age_seconds is not None else "нет данных"
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
        tooltip_parts = [
            f"МИР: {always_on.mission_phase or 'нет данных'}",
            f"СВЯЗЬ: {link_raw or 'нет данных'} | задержка {latency} | потери {loss}",
            f"АКТУАЛ: возраст {age_hint}",
            f"СЕНС: {sens_raw or 'нет данных'}"
            + (f" | {derived.sensor_trust_summary}" if derived.sensor_trust_summary else ""),
            f"УПР: {authority_raw}",
            f"СОБЫТ: {self._state.events_count}",
        ]
        if mode_value and mode_value.lower() not in {"n/a", "unknown", "нет данных", "none"}:
            tooltip_parts.append(f"режим: {mode_value}")
        if always_on.last_contact_timestamp:
            tooltip_parts.append(f"RX: {always_on.last_contact_timestamp}")
        tooltip_parts.append("клик/клавиши: МИР·СВЯЗЬ·АКТУАЛ → F7 | СЕНС → F3 | УПР → F6")
        self.tooltip = "\n".join(tooltip_parts)
        self.update("\n".join((line_1, line_2)))
