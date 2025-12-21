"""
Shell OS unit tests.

Important: tests may call compose() directly without a running Textual App.
Panels must not crash with NoActiveAppError.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


# Add service directory to sys.path for `from main import ...` imports (same pattern as operator_console tests).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import ShellOSApp  # noqa: E402
from ui.resources_panel import ResourcesPanel  # noqa: E402
from ui.services_panel import ServicesPanel  # noqa: E402
from ui.system_panel import SystemPanel  # noqa: E402


class TestPanels:
    def test_system_panel_compose_does_not_crash(self):
        panel = SystemPanel()
        with patch("textual.widgets.Label") as mock_label:
            with patch("textual.widgets.DataTable") as mock_table:
                mock_label.return_value = MagicMock()
                mock_table.return_value = MagicMock()
                widgets = list(panel.compose())
                assert len(widgets) >= 1

    def test_resources_panel_compose_does_not_crash(self):
        panel = ResourcesPanel()
        with patch("textual.widgets.Label") as mock_label:
            with patch("textual.widgets.DataTable") as mock_table:
                mock_label.return_value = MagicMock()
                mock_table.return_value = MagicMock()
                widgets = list(panel.compose())
                assert len(widgets) >= 1

    def test_services_panel_compose_does_not_crash(self):
        panel = ServicesPanel()
        with patch("textual.widgets.Label") as mock_label:
            with patch("textual.widgets.DataTable") as mock_table:
                mock_label.return_value = MagicMock()
                mock_table.return_value = MagicMock()
                widgets = list(panel.compose())
                assert len(widgets) >= 1


class TestApp:
    @pytest.mark.asyncio
    async def test_app_compose_structure(self):
        app = ShellOSApp()
        with patch("textual.widgets.Header") as mock_header:
            with patch("textual.widgets.Footer") as mock_footer:
                with patch("textual.widgets.TabbedContent") as mock_tabs:
                    with patch("textual.widgets.TabPane") as mock_pane:
                        mock_header.return_value = MagicMock()
                        mock_footer.return_value = MagicMock()
                        mock_tabs.return_value = MagicMock()
                        mock_pane.return_value = MagicMock()
                        widgets = list(app.compose())
                        assert len(widgets) >= 2

