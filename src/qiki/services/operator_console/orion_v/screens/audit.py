from __future__ import annotations

from typing import Any

from textual.widgets import Static


class OrionVAuditScreen(Static):
    """Operator audit trail view (F6)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._lines: list[str] = []
        self._summary = ""

    def on_mount(self) -> None:
        self._refresh_text()

    def set_state(self, *, lines: list[str], summary: str) -> None:
        self._lines = lines
        self._summary = summary
        self._refresh_text()

    def _refresh_text(self) -> None:
        body = ["[F6] Журнал действий", "", f"Фильтр: {self._summary or 'все'}", ""]
        body.extend(self._lines if self._lines else ["Записей аудита пока нет"])
        self.update("\n".join(body))
