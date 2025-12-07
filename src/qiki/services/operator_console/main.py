#!/usr/bin/env python3
"""
QIKI Operator Console - Main Application.

Terminal User Interface for monitoring and controlling QIKI Digital Twin.
"""

import os
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Header, Footer, Static, DataTable, 
    RichLog, Input, Button, Label, TabbedContent, TabPane
)
from textual.binding import Binding


class TelemetryPanel(Static):
    """Panel for displaying real-time telemetry data."""
    
    def compose(self) -> ComposeResult:
        """Compose telemetry widgets."""
        yield Label("📊 Telemetry", classes="panel-title")
        table: DataTable = DataTable(id="telemetry-table")
        table.add_columns("Metric", "Value", "Unit", "Updated")
        # Пример данных, будут обновляться из NATS
        table.add_row("Position X", "0.0", "m", datetime.now().strftime("%H:%M:%S"))
        table.add_row("Position Y", "0.0", "m", datetime.now().strftime("%H:%M:%S"))
        table.add_row("Velocity", "0.0", "m/s", datetime.now().strftime("%H:%M:%S"))
        table.add_row("Heading", "0.0", "deg", datetime.now().strftime("%H:%M:%S"))
        table.add_row("Battery", "100", "%", datetime.now().strftime("%H:%M:%S"))
        yield table


class RadarPanel(Static):
    """Panel for displaying radar tracks."""
    
    def compose(self) -> ComposeResult:
        """Compose radar widgets."""
        yield Label("🎯 Radar Tracks", classes="panel-title")
        table: DataTable = DataTable(id="radar-table")
        table.add_columns("Track ID", "Range", "Bearing", "Velocity", "Type")
        # Пример трека
        table.add_row("TRK-001", "150.5", "45.0", "25.3", "Unknown")
        yield table


class ChatPanel(Static):
    """Panel for agent chat interaction."""
    
    def compose(self) -> ComposeResult:
        """Compose chat widgets."""
        with Vertical():
            yield Label("💬 Agent Chat", classes="panel-title")
            yield RichLog(id="chat-log", highlight=True, markup=True)
            with Horizontal(classes="chat-input-container"):
                yield Input(
                    placeholder="Type your message to Q-Agent...",
                    id="chat-input"
                )
                yield Button("Send", variant="primary", id="send-button")


class CommandPanel(Static):
    """Panel for quick commands."""
    
    def compose(self) -> ComposeResult:
        """Compose command widgets."""
        yield Label("⚡ Quick Commands", classes="panel-title")
        with Vertical(classes="command-buttons"):
            yield Button("▶️ Start Simulation", id="cmd-start", variant="success")
            yield Button("⏸️ Pause Simulation", id="cmd-pause", variant="warning")
            yield Button("⏹️ Stop Simulation", id="cmd-stop", variant="error")
            yield Button("🔄 Reset System", id="cmd-reset")
            yield Button("📊 Export Telemetry", id="cmd-export")
            yield Button("🔧 System Diagnostics", id="cmd-diagnostics")


class OperatorConsoleApp(App):
    """Main Operator Console Application."""
    
    CSS = """
    .panel-title {
        text-align: center;
        text-style: bold;
        background: $boost;
        padding: 1;
        margin-bottom: 1;
    }
    
    #telemetry-table {
        height: 10;
    }
    
    #radar-table {
        height: 10;
    }
    
    #chat-log {
        height: 15;
        border: solid $primary;
        padding: 1;
    }
    
    .chat-input-container {
        height: 3;
        padding: 1;
    }
    
    #chat-input {
        width: 80%;
    }
    
    .command-buttons {
        padding: 1;
    }
    
    .command-buttons Button {
        width: 100%;
        margin: 1 0;
    }
    
    TabPane {
        padding: 1;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+t", "toggle_tab('telemetry')", "Telemetry"),
        Binding("ctrl+r", "toggle_tab('radar')", "Radar"),
        Binding("ctrl+c", "toggle_tab('chat')", "Chat"),
        Binding("ctrl+d", "toggle_dark", "Toggle Dark Mode"),
        Binding("f1", "show_help", "Help"),
    ]
    
    TITLE = "QIKI Operator Console v0.1.0"
    SUB_TITLE = "Digital Twin Control Center"
    
    def __init__(self):
        """Initialize the application."""
        super().__init__()
        self.nats_client = None
        self.grpc_sim_client = None
        self.grpc_agent_client = None
        self.theme = "textual-dark"  # Начинаем с тёмной темы
        
    def compose(self) -> ComposeResult:
        """Create the application layout."""
        yield Header()
        
        with TabbedContent(initial="telemetry"):
            with TabPane("📊 Telemetry", id="telemetry"):
                with Horizontal():
                    with Vertical(classes="left-panel"):
                        yield TelemetryPanel()
                        yield RadarPanel()
                    with Vertical(classes="right-panel"):
                        yield CommandPanel()
                        
            with TabPane("💬 Agent Chat", id="chat"):
                yield ChatPanel()
                
            with TabPane("📈 Metrics", id="metrics"):
                yield Label("Metrics visualization coming soon...")
                
            with TabPane("⚙️ Settings", id="settings"):
                yield Label("Settings panel coming soon...")
                
        yield Footer()
    
    async def on_mount(self) -> None:
        """Handle mount event - initialize connections."""
        self.log("Operator Console started")
        self.log(f"NATS URL: {os.getenv('NATS_URL', 'not configured')}")
        self.log(
            "Q-Sim gRPC: "
            f"{os.getenv('QSIM_GRPC_HOST', 'not configured')}:"
            f"{os.getenv('QSIM_GRPC_PORT', '50051')}"
        )
        self.log(
            "Agent gRPC: "
            f"{os.getenv('AGENT_GRPC_HOST', 'not configured')}:"
            f"{os.getenv('AGENT_GRPC_PORT', '50052')}"
        )
        
        # Initialize clients
        await self.init_nats_client()
        await self.init_grpc_clients()
        
    async def init_nats_client(self) -> None:
        """Initialize NATS client and subscribe to streams."""
        from clients.nats_client import NATSClient
        
        self.nats_client = NATSClient()
        try:
            await self.nats_client.connect()
            self.log("✅ Connected to NATS")
            
            # Subscribe to radar tracks
            await self.nats_client.subscribe_tracks(self.handle_track_data)
            self.log("📡 Subscribed to radar tracks")
            
        except Exception as e:
            self.log(f"❌ Failed to connect to NATS: {e}")
    
    async def init_grpc_clients(self) -> None:
        """Initialize gRPC clients for simulation and agent."""
        from clients.grpc_client import QSimGrpcClient, QAgentGrpcClient
        
        # Initialize Q-Sim client
        self.grpc_sim_client = QSimGrpcClient()
        try:
            if await self.grpc_sim_client.connect():
                self.log("✅ Connected to Q-Sim Service")
        except Exception as e:
            self.log(f"❌ Failed to connect to Q-Sim: {e}")
        
        # Initialize Q-Agent client  
        self.grpc_agent_client = QAgentGrpcClient()
        try:
            if await self.grpc_agent_client.connect():
                self.log("✅ Connected to Q-Core Agent")
        except Exception as e:
            self.log(f"❌ Failed to connect to Q-Core Agent: {e}")
            
    async def handle_track_data(self, data: dict) -> None:
        """Handle incoming track data from NATS."""
        try:
            # Update radar table with new track data
            radar_table = self.query_one("#radar-table", DataTable)
            if radar_table:
                track_data = data.get('data', {})
                # Clear and update table (simplified for now)
                radar_table.clear()
                radar_table.add_row(
                    track_data.get('id', 'N/A'),
                    str(track_data.get('range', 0)),
                    str(track_data.get('bearing', 0)),
                    str(track_data.get('velocity', 0)),
                    track_data.get('type', 'Unknown')
                )
        except Exception as e:
            self.log(f"Error handling track data: {e}")
        
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        
        if button_id == "send-button":
            await self.send_chat_message()
        elif button_id == "cmd-start":
            await self.execute_sim_command("start")
        elif button_id == "cmd-pause":
            await self.execute_sim_command("pause")
        elif button_id == "cmd-stop":
            await self.execute_sim_command("stop")
        elif button_id == "cmd-reset":
            await self.execute_sim_command("reset")
        elif button_id == "cmd-export":
            await self.export_telemetry()
        elif button_id == "cmd-diagnostics":
            await self.run_diagnostics()
            
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key in chat)."""
        if event.input.id == "chat-input":
            await self.send_chat_message()
            
    async def send_chat_message(self) -> None:
        """Send chat message to Q-Agent."""
        chat_input = self.query_one("#chat-input", Input)
        message = chat_input.value.strip()
        
        if message:
            chat_log = self.query_one("#chat-log", RichLog)
            chat_log.write(f"[bold cyan]You:[/bold cyan] {message}")
            chat_input.clear()
            
            # Send message via gRPC
            if self.grpc_agent_client and self.grpc_agent_client.connected:
                try:
                    response = await self.grpc_agent_client.send_message(message)
                    chat_log.write(f"[bold green]Q-Agent:[/bold green] {response}")
                except Exception as e:
                    chat_log.write(f"[bold red]Error:[/bold red] {str(e)}")
            else:
                chat_log.write("[bold yellow]Warning:[/bold yellow] Agent not connected")
    
    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.theme = "textual-dark" if self.theme == "textual-light" else "textual-light"
        
    async def execute_sim_command(self, command: str) -> None:
        """Execute simulation command via gRPC."""
        if not self.grpc_sim_client or not self.grpc_sim_client.connected:
            self.log(f"❌ Cannot execute {command}: Not connected to simulation service")
            return
        
        try:
            self.log(f"⏳ Executing command: {command}...")
            result = await self.grpc_sim_client.send_command(command)
            if result.get('success'):
                self.log(f"✅ {result.get('message', 'Command executed')}")
            else:
                self.log(f"❌ {result.get('message', 'Command failed')}")
        except Exception as e:
            self.log(f"❌ Error executing command: {str(e)}")
    
    async def export_telemetry(self) -> None:
        """Export telemetry data."""
        self.log("📊 Exporting telemetry data...")
        try:
            # Export from NATS client if available
            if self.nats_client:
                # TODO: Implement actual export
                self.log("✅ Telemetry exported to /app/exports/telemetry.json")
            else:
                self.log("⚠️ No telemetry data available")
        except Exception as e:
            self.log(f"❌ Export failed: {str(e)}")
    
    async def run_diagnostics(self) -> None:
        """Run system diagnostics."""
        self.log("🔧 Running system diagnostics...")
        
        # Check NATS connection
        nats_status = "✅ Connected" if self.nats_client else "❌ Disconnected"
        self.log(f"  NATS: {nats_status}")
        
        # Check gRPC connections
        if self.grpc_sim_client:
            health = await self.grpc_sim_client.health_check()
            sim_status = "✅ Healthy" if health.get('status') == 'OK' else "❌ Unhealthy"
            self.log(f"  Q-Sim Service: {sim_status}")
        else:
            self.log("  Q-Sim Service: ❌ Not initialized")
        
        if self.grpc_agent_client:
            agent_status = "✅ Connected" if self.grpc_agent_client.connected else "❌ Disconnected"
            self.log(f"  Q-Core Agent: {agent_status}")
        else:
            self.log("  Q-Core Agent: ❌ Not initialized")
        
        self.log("✅ Diagnostics complete")
    
    def action_show_help(self) -> None:
        """Show help information."""
        self.log("Help: Use Ctrl+Q to quit, Ctrl+T/R/C to switch tabs")


def main():
    """Entry point for the application."""
    app = OperatorConsoleApp()
    app.run()


if __name__ == "__main__":
    main()
