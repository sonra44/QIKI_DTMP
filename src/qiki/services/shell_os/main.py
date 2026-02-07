"""
Shell OS — Textual TUI service (no-mocks).

Shows only real, locally available system / runtime information.
If a data source is unavailable, renders a truthful status instead of fake values.
"""

from __future__ import annotations

import os
from importlib import import_module
from typing import Any
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static
from textual.containers import Vertical


def _has_active_textual_app() -> bool:
    """True when Textual active_app context exists (real runtime, not direct unit-test compose())."""
    try:
        from textual._context import active_app  # type: ignore

        active_app.get()
        return True
    except Exception:
        return False


class ShellOSApp(App):
    TITLE = "QIKI — Shell OS"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]

    CSS = """
    Screen { background: $surface; }
    .panel-title { text-style: bold; padding: 0 1; }
    .panel-wrap { padding: 1; }
    """

    @staticmethod
    def _load_panels() -> tuple[type[Any], type[Any], type[Any]]:
        if __package__:
            resources_mod_name = "qiki.services.shell_os.ui.resources_panel"
            services_mod_name = "qiki.services.shell_os.ui.services_panel"
            system_mod_name = "qiki.services.shell_os.ui.system_panel"
        else:
            # Legacy direct execution from this directory.
            resources_mod_name = "ui.resources_panel"
            services_mod_name = "ui.services_panel"
            system_mod_name = "ui.system_panel"
        resources_panel_mod = import_module(resources_mod_name)
        services_panel_mod = import_module(services_mod_name)
        system_panel_mod = import_module(system_mod_name)
        return system_panel_mod.SystemPanel, resources_panel_mod.ResourcesPanel, services_panel_mod.ServicesPanel

    def compose(self) -> ComposeResult:
        # Lazy imports so unit tests can patch `textual.widgets.*` if needed.
        from textual.widgets import Header, Footer, TabbedContent, TabPane
        SystemPanel, ResourcesPanel, ServicesPanel = self._load_panels()

        yield Header()

        with TabbedContent(initial="system"):
            yield TabPane("🧠 System", SystemPanel(), id="system")
            yield TabPane("📊 Resources", ResourcesPanel(), id="resources")
            yield TabPane("🧩 Services", ServicesPanel(), id="services")
            yield TabPane(
                "ℹ️ About",
                Vertical(
                    Static(
                        "Shell OS показывает только реальные данные.\n"
                        "Если источник недоступен — вы увидите честный статус/ошибку.",
                        classes="panel-wrap",
                    ),
                    Static(
                        f"PID: {os.getpid()}\nCWD: {os.getcwd()}",
                        classes="panel-wrap",
                    ),
                ),
                id="about",
            )

        yield Footer()

    async def on_mount(self) -> None:
        # In unit tests compose() can be called without an active app.
        if not _has_active_textual_app():
            return

        # Refresh panels periodically (best-effort).
        self.set_interval(1.5, self.action_refresh)

    def action_refresh(self) -> None:
        # Each panel handles its own refresh (best-effort).
        for panel_id in ("system-panel", "resources-panel", "services-panel"):
            try:
                panel = self.query_one(f"#{panel_id}", Static)
                refresh = getattr(panel, "refresh_data", None)
                if callable(refresh):
                    refresh()
            except Exception:
                continue


if __name__ == "__main__":
    ShellOSApp().run()
