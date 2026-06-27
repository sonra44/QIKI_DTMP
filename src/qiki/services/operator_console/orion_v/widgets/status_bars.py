from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Static

from qiki.services.operator_console.orion_v.operator_state import OperatorShellState

_STATUS_VARIANT = {
    "normal": "success",
    "warning": "warning",
    "critical": "error",
    "unavailable": "default",
}


class OrionVStatusBars(Static):
    """Compact system chips for the safety and health strip."""

    DEFAULT_CSS = """
    OrionVStatusBars {
        height: auto;
        layout: vertical;
    }

    OrionVStatusBars #orionv-status-title {
        height: auto;
        color: $text-muted;
    }

    OrionVStatusBars #orionv-status-chip-row {
        height: auto;
        layout: horizontal;
    }

    OrionVStatusBars #orionv-status-chip-row Button {
        width: 1fr;
        min-width: 14;
        margin: 0 1 0 0;
    }

    OrionVStatusBars #orionv-status-chip-row Button:hover {
        text-style: bold;
        background: $boost;
    }

    OrionVStatusBars #orionv-status-chip-row Button:focus {
        text-style: bold;
    }
    """

    class MetricActionTriggered(Message):
        """Emitted when operator clicks a metric action button."""

        def __init__(self, action: str, target: str) -> None:
            self.action = action
            self.target = target
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._state = OperatorShellState.empty()
        self._last_rendered_states: tuple[str, ...] | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="orionv-status-title")
        with Horizontal(id="orionv-status-chip-row"):
            for slug in ("power", "thermal", "propulsion", "hull", "compute", "qiki"):
                yield Button("", id=f"orionv-status-{slug}-action", compact=True)

    def on_mount(self) -> None:
        self._refresh()

    def set_state(self, state: OperatorShellState) -> None:
        self._state = state
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if not button_id.startswith("orionv-status-") or not button_id.endswith("-action"):
            return
        slug = button_id.removeprefix("orionv-status-").removesuffix("-action").strip().lower()
        chip = next((item for item in self._state.chips if item.slug == slug), None)
        if chip is None:
            return
        self.post_message(self.MetricActionTriggered(chip.action, chip.target))

    def _refresh(self) -> None:
        rendered_states = tuple(
            f"{chip.slug}:{chip.status}:{chip.short_summary}:{chip.hint}:{chip.numeric_anchor}:{chip.stale}"
            for chip in self._state.chips
        )
        if rendered_states == self._last_rendered_states:
            return
        self._last_rendered_states = rendered_states

        alert_summary = self._state.always_on.alert_summary
        safe_mode = self._state.always_on.safe_envelope_state or "nominal"
        title = self.query_one("#orionv-status-title", Static)
        title.update(
            f"КР{alert_summary.critical_count}/ПР{alert_summary.warning_count}/ВН{alert_summary.attention_count}"
            f" | контур {safe_mode}"
            f" | риск {self._state.derived.mission_risk_state or 'unknown'}"
        )
        for chip in self._state.chips:
            button = self.query_one(f"#orionv-status-{chip.slug}-action", Button)
            details: list[str] = [chip.label, chip.status.upper(), chip.short_summary]
            if chip.stale:
                details.append("stale")
            elif chip.severity != "normal" and isinstance(chip.numeric_anchor, (int, float)):
                details.append(f"{chip.numeric_anchor:.1f}")
            # Leading marker + tooltip make the chip read as an actionable control
            # (the strip was clickable but gave no affordance — operator didn't know to click).
            button.label = "▸ " + " | ".join(part for part in details if part)
            button.variant = _STATUS_VARIANT[chip.severity]
            button.tooltip = (
                f"Клик → {chip.action}: {chip.target}"
                if getattr(chip, "action", "")
                else f"{chip.label}: открыть подсистему"
            )
