from __future__ import annotations

from typing import Any

from textual.widgets import Static


class OrionVDeepDiveScreen(Static):
    """Deep-dive events/incidents view (F3)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._lines: list[str] = []
        self._incidents: list[dict[str, str]] = []
        self._selected_incident_id: str | None = None
        self._filter_summary = ""
        self._safe_mode: dict[str, Any] = {}

    def on_mount(self) -> None:
        self._refresh_text()

    def set_state(
        self,
        *,
        lines: list[str],
        incidents: list[dict[str, str]],
        selected_incident_id: str | None,
        filter_summary: str,
        safe_mode: dict[str, Any] | None = None,
    ) -> None:
        self._lines = lines
        self._incidents = incidents
        self._selected_incident_id = selected_incident_id
        self._filter_summary = filter_summary
        self._safe_mode = safe_mode or {}
        self._refresh_text()

    def _refresh_text(self) -> None:
        body: list[str] = [
            "[F3] Глубокий анализ",
            "",
            "Инциденты (Вверх/Вниз, A=подтвердить, X=снять, click=выбрать):",
        ]
        if not self._incidents:
            body.append("Нет активных C/A инцидентов")
        else:
            for incident in self._incidents:
                incident_id = incident["id"]
                marker = ">" if incident_id == self._selected_incident_id else " "
                select_action = _action_link("select_incident", incident_id)
                body.append(
                    f"{marker} [{incident['severity']}] {incident_id} - {incident['description']} {select_action}"
                )

        body.extend(["", "Безопасность (Q-Core authority):"])
        body.extend(_safe_mode_lines(self._safe_mode))
        body.extend(["", f"События: {self._filter_summary or 'без фильтров'}"])
        body.extend(self._lines if self._lines else ["Событий пока нет"])
        self.update("\n".join(body))


def _safe_mode_lines(safe_mode: dict[str, Any]) -> list[str]:
    active = safe_mode.get("active")
    reason = str(safe_mode.get("reason") or "").strip() or "Нет данных"
    authority = str(safe_mode.get("authority") or "").strip() or "q-core-agent(events)"
    if active is True:
        state = "ВКЛЮЧЕН"
    elif active is False:
        state = "выключен"
    else:
        state = "нет данных"
    return [
        f"• SAFE MODE: {state}",
        f"• Причина: {reason}",
        f"• Authority: {authority}",
    ]


def _action_link(action: str, value: str) -> str:
    safe_value = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"[@click={action}('{safe_value}')]select/click[/]"
