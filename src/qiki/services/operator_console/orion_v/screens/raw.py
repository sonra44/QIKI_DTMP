from __future__ import annotations

from rich.text import Text
from typing import Any

from textual.widgets import Static


class OrionVRawScreen(Static):
    """Operator console history view (F4)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._text = ""

    def on_mount(self) -> None:
        self._refresh_text()

    def set_text(self, text: str) -> None:
        self._text = text
        self._refresh_text()

    def _refresh_text(self) -> None:
        body = self._text if self._text else "История команд и ответов пока пуста"
        # Console history must be rendered literally; payload-like strings must not be interpreted as markup.
        self.update(Text("\n".join(["[F4] Консоль/Console", "", body])))
