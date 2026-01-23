"""
Tests for UI components and panels from main application.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from qiki.services.operator_console.main import TelemetryPanel, RadarPanel, ChatPanel, CommandPanel, OperatorConsoleApp


class TestTelemetryPanel:
    """Test TelemetryPanel widget."""

    @pytest.fixture
    def telemetry_panel(self):
        """Create a TelemetryPanel instance."""
        return TelemetryPanel()

    def test_panel_initialization(self, telemetry_panel):
        """Test that TelemetryPanel initializes correctly."""
        assert telemetry_panel is not None
        assert telemetry_panel.__class__.__name__ == "TelemetryPanel"

    def test_panel_compose_structure(self, telemetry_panel):
        """Test that compose method returns widgets."""
        with patch("textual.widgets.Label") as mock_label:
            with patch("textual.widgets.DataTable") as mock_table:
                mock_label.return_value = MagicMock()
                mock_table.return_value = MagicMock()

                # Call compose and get generator
                compose_generator = telemetry_panel.compose()
                widgets = list(compose_generator)

                # Should have at least a label and table
                assert len(widgets) >= 1


class TestRadarPanel:
    """Test RadarPanel widget."""

    @pytest.fixture
    def radar_panel(self):
        """Create a RadarPanel instance."""
        return RadarPanel()

    def test_panel_initialization(self, radar_panel):
        """Test that RadarPanel initializes correctly."""
        assert radar_panel is not None
        assert radar_panel.__class__.__name__ == "RadarPanel"

    def test_panel_compose_structure(self, radar_panel):
        """Test that compose method returns widgets."""
        with patch("textual.widgets.Label") as mock_label:
            with patch("textual.widgets.DataTable") as mock_table:
                mock_label.return_value = MagicMock()
                mock_table.return_value = MagicMock()

                # Call compose and get generator
                compose_generator = radar_panel.compose()
                widgets = list(compose_generator)

                # Should have at least a label and table
                assert len(widgets) >= 1


class TestChatPanel:
    """Test ChatPanel widget."""

    @pytest.fixture
    def chat_panel(self):
        """Create a ChatPanel instance."""
        return ChatPanel()

    def test_panel_initialization(self, chat_panel):
        """Test that ChatPanel initializes correctly."""
        assert chat_panel is not None
        assert chat_panel.__class__.__name__ == "ChatPanel"

    def test_panel_compose_structure(self, chat_panel):
        """Test that compose method returns widgets."""
        with patch("textual.widgets.Label") as mock_label:
            with patch("textual.widgets.RichLog") as mock_log:
                with patch("textual.widgets.Input") as mock_input:
                    with patch("textual.widgets.Button") as mock_button:
                        mock_label.return_value = MagicMock()
                        mock_log.return_value = MagicMock()
                        mock_input.return_value = MagicMock()
                        mock_button.return_value = MagicMock()

                        # Call compose and get generator
                        compose_generator = chat_panel.compose()
                        widgets = list(compose_generator)

                        # Should have vertical container
                        assert len(widgets) >= 1


class TestCommandPanel:
    """Test CommandPanel widget."""

    @pytest.fixture
    def command_panel(self):
        """Create a CommandPanel instance."""
        return CommandPanel()

    def test_panel_initialization(self, command_panel):
        """Test that CommandPanel initializes correctly."""
        assert command_panel is not None
        assert command_panel.__class__.__name__ == "CommandPanel"

    def test_panel_compose_structure(self, command_panel):
        """Test that compose method returns widgets."""
        with patch("textual.widgets.Label") as mock_label:
            with patch("textual.widgets.Button") as mock_button:
                mock_label.return_value = MagicMock()
                mock_button.return_value = MagicMock()

                # Call compose and get generator
                compose_generator = command_panel.compose()
                widgets = list(compose_generator)

                # Should have at least a label
                assert len(widgets) >= 1


class TestOperatorConsoleApp:
    """Test main OperatorConsoleApp class."""

    @pytest.fixture
    def app(self):
        """Create an OperatorConsoleApp instance."""
        return OperatorConsoleApp()

    def test_app_initialization(self, app):
        """Test that OperatorConsoleApp initializes correctly."""
        assert app is not None
        assert app.__class__.__name__ == "OperatorConsoleApp"

        # Check initial state
        assert app.nats_client is None
        assert app.grpc_sim_client is None
        assert app.grpc_agent_client is None
        assert app.theme == "textual-dark"

    def test_app_compose_structure(self, app):
        """Test that compose method returns proper structure."""
        with patch("textual.widgets.Header") as mock_header:
            with patch("textual.widgets.Footer") as mock_footer:
                with patch("textual.widgets.TabbedContent") as mock_tabs:
                    mock_header.return_value = MagicMock()
                    mock_footer.return_value = MagicMock()
                    mock_tabs.return_value = MagicMock()

                    # Call compose and get generator
                    compose_generator = app.compose()
                    widgets = list(compose_generator)

                    # Should have header, tabs, and footer
                    assert len(widgets) >= 2

    @pytest.mark.asyncio
    async def test_app_mount_initialization(self, app):
        """Test on_mount event handler."""
        with patch.object(app, "init_nats_client") as mock_nats:
            with patch.object(app, "init_grpc_clients") as mock_grpc:
                with patch.object(app, "log") as mock_log:
                    mock_nats.return_value = AsyncMock()
                    mock_grpc.return_value = AsyncMock()

                    await app.on_mount()

                    # Should have called initialization methods
                    mock_nats.assert_called_once()
                    mock_grpc.assert_called_once()
                    mock_log.assert_called()

    @pytest.mark.asyncio
    async def test_init_nats_client(self, app):
        """Test NATS client initialization."""
        with patch("qiki.services.operator_console.clients.nats_client.NATSClient") as mock_nats_class:
            mock_client = AsyncMock()
            mock_nats_class.return_value = mock_client
            mock_client.connect.return_value = None
            mock_client.subscribe_tracks.return_value = None

            with patch.object(app, "log") as mock_log:
                await app.init_nats_client()

                assert app.nats_client is mock_client
                mock_client.connect.assert_called_once()
                mock_client.subscribe_tracks.assert_called_once()
                mock_log.assert_called()

    @pytest.mark.asyncio
    async def test_init_grpc_clients(self, app):
        """Test gRPC clients initialization."""
        with patch("qiki.services.operator_console.clients.grpc_client.QSimGrpcClient") as mock_sim_class:
            with patch("qiki.services.operator_console.clients.grpc_client.QAgentGrpcClient") as mock_agent_class:
                mock_sim_client = AsyncMock()
                mock_agent_client = AsyncMock()
                mock_sim_class.return_value = mock_sim_client
                mock_agent_class.return_value = mock_agent_client

                mock_sim_client.connect.return_value = True
                mock_agent_client.connect.return_value = True

                with patch.object(app, "log") as mock_log:
                    await app.init_grpc_clients()

                    assert app.grpc_sim_client is mock_sim_client
                    assert app.grpc_agent_client is mock_agent_client
                    mock_sim_client.connect.assert_called_once()
                    mock_agent_client.connect.assert_called_once()
                    mock_log.assert_called()

    @pytest.mark.asyncio
    async def test_handle_track_data(self, app):
        """Test track data handling."""
        mock_table = MagicMock()

        with patch.object(app, "query_one", return_value=mock_table):
            test_data = {"data": {"id": "TRK-001", "range": 150.5, "bearing": 45.0, "velocity": 25.3, "type": "Ship"}}

            await app.handle_track_data(test_data)

            # Should have cleared and updated table
            mock_table.clear.assert_called_once()
            mock_table.add_row.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_chat_message(self, app):
        """Test sending chat message."""
        mock_input = MagicMock()
        mock_input.value = "Hello agent"
        mock_log = MagicMock()
        mock_agent_client = AsyncMock()
        mock_agent_client.connected = True
        mock_agent_client.send_message.return_value = "Hello! How can I help?"

        app.grpc_agent_client = mock_agent_client

        with patch.object(app, "query_one") as mock_query:
            mock_query.side_effect = [mock_input, mock_log]

            await app.send_chat_message()

            mock_agent_client.send_message.assert_called_once_with("Hello agent")
            mock_input.clear.assert_called_once()
            assert mock_log.write.call_count >= 2  # User message + agent response

    @pytest.mark.asyncio
    async def test_execute_sim_command(self, app):
        """Test executing simulation commands (published via NATS)."""
        mock_nats_client = AsyncMock()
        app.nats_client = mock_nats_client

        with patch.object(app, "log") as mock_log:
            await app.execute_sim_command("start")

            mock_nats_client.publish_command.assert_called_once()
            mock_log.assert_called()

    @pytest.mark.asyncio
    async def test_export_telemetry(self, app):
        """Test telemetry export."""
        mock_nats_client = MagicMock()
        app.nats_client = mock_nats_client

        with patch.object(app, "log") as mock_log:
            await app.export_telemetry()

            # Should log export process
            mock_log.assert_called()

    @pytest.mark.asyncio
    async def test_run_diagnostics(self, app):
        """Test system diagnostics."""
        mock_sim_client = AsyncMock()
        mock_sim_client.health_check.return_value = {"status": "OK"}
        mock_agent_client = MagicMock()
        mock_agent_client.connected = True

        app.grpc_sim_client = mock_sim_client
        app.grpc_agent_client = mock_agent_client
        app.nats_client = MagicMock()

        with patch.object(app, "log") as mock_log:
            await app.run_diagnostics()

            mock_sim_client.health_check.assert_called_once()
            # Should log diagnostics results
            assert mock_log.call_count >= 4  # Multiple diagnostic logs

    def test_action_toggle_dark(self, app):
        """Test dark mode toggle action."""
        # Start with dark theme
        assert app.theme == "textual-dark"

        app.action_toggle_dark()
        assert app.theme == "textual-light"

        app.action_toggle_dark()
        assert app.theme == "textual-dark"

    def test_action_show_help(self, app):
        """Test show help action."""
        with patch.object(app, "log") as mock_log:
            app.action_show_help()
            mock_log.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
