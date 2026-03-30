from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmDialog(ModalScreen[bool]):
    """Simple confirmation dialog for incident actions."""

    BINDINGS = [
        ("y", "confirm_yes", "Подтвердить"),
        ("n", "confirm_no", "Отмена"),
        ("enter", "confirm_yes", "Подтвердить"),
        ("escape", "confirm_no", "Отмена"),
    ]

    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }

    #orionv-confirm {
        width: 72;
        border: round $warning;
        padding: 1 2;
        background: $surface;
    }

    #orionv-confirm-actions {
        height: 3;
        align: center middle;
    }

    #orionv-confirm-actions Button {
        margin: 0 1;
        width: 14;
    }
    """

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        yield Static(self._prompt, id="orionv-confirm")
        with Horizontal(id="orionv-confirm-actions"):
            yield Button("Подтвердить", id="orionv-confirm-yes", variant="primary")
            yield Button("Отмена", id="orionv-confirm-no")

    def action_confirm_yes(self) -> None:
        self.dismiss(True)

    def action_confirm_no(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "orionv-confirm-yes":
            self.dismiss(True)
        if event.button.id == "orionv-confirm-no":
            self.dismiss(False)
