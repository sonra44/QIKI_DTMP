from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Button, Static

from qiki.services.operator_console.orion_v.operator_state import OperatorShellState
from qiki.services.operator_console.orion_v.operator_state import (
    build_level0_alerts as _build_level0_alerts,
)


def build_level0_alerts(*args: Any, **kwargs: Any):
    return _build_level0_alerts(*args, **kwargs)


class OrionVAlertsOverlay(Static):
    """Compact alert summary for the safety strip."""

    class IncidentSelected(Message):
        """Emitted when operator clicks an incident-backed alert in overlay."""

        def __init__(self, incident_id: str) -> None:
            self.incident_id = incident_id
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._state = OperatorShellState.empty()

    def compose(self) -> ComposeResult:
        yield Static("", id="orionv-overlay-summary")
        yield Button("", id="orionv-overlay-focus", classes="hidden", compact=True)

    def set_state(self, state: OperatorShellState) -> None:
        self._state = state
        self._refresh_text()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        focus_alert = self._state.always_on.alert_summary.focus_alert
        if (event.button.id or "") == "orionv-overlay-focus" and focus_alert and focus_alert.incident_id:
            self.post_message(self.IncidentSelected(focus_alert.incident_id))

    def _refresh_text(self) -> None:
        summary_state = self._state.always_on.alert_summary
        focus_alert = summary_state.focus_alert
        # SAFETY_HEALTH_STRIP_CANON / ADR-0016 + DISPLAY_CANON строка №3 (dark
        # cockpit): на номинале overlay не занимает даже пустой строки — виджет
        # схлопывается целиком и появляется только с живым алертом.
        self.display = focus_alert is not None
        if focus_alert is None:
            summary = ""
        else:
            next_hint = f" | дальше {focus_alert.next_action_hint}" if focus_alert.next_action_hint else ""
            stale = " | stale" if summary_state.stale else ""
            summary = (
                "Алерты "
                f"C{summary_state.critical_count}/W{summary_state.warning_count}/A{summary_state.attention_count}"
                f" | фокус [{focus_alert.severity.upper()}] {focus_alert.title}"
                f" | эффект {focus_alert.operator_effect}"
                f"{next_hint}{stale}"
            )
        self.query_one("#orionv-overlay-summary", Static).update(summary)

        focus_button = self.query_one("#orionv-overlay-focus", Button)
        if focus_alert and focus_alert.incident_id:
            focus_button.label = f"Фокус {focus_alert.incident_id}"
            focus_button.remove_class("hidden")
            focus_button.variant = "primary"
        else:
            focus_button.add_class("hidden")
