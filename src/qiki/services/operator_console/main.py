#!/usr/bin/env python3
# ruff: noqa: RUF002

"""
QIKI Operator Console - LEGACY / ARCHIVE ENTRYPOINT.

⚠️  НЕ РАЗВИВАТЬ / НЕ ИСПОЛЬЗОВАТЬ как основную консоль.

Причина:
  - Каноническая операторская консоль проекта — ORION: `main_orion.py`
    (см. `docker-compose.operator.yml`, там запускается именно ORION).
  - Этот файл исторически содержал host/VPS метрики (psutil) и частично
    дублировал интерфейсы ORION, что создаёт риск "двух линий правды".

Политика:
  - Оставлен только как архив/референс (и для тестового окружения виджетов).
  - Для запуска требуется явное подтверждение переменной окружения:
      ALLOW_LEGACY_OPERATOR_CONSOLE=1
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Static, TabbedContent
from textual.binding import Binding

from ui.profile_panel import ProfilePanel
from widgets.metrics_panel import MetricsPanel
from clients.metrics_client import MetricsClient


def _has_active_textual_app() -> bool:
    """Return True when Textual's active_app context is available (i.e., real runtime compose)."""
    try:
        from textual._context import active_app  # type: ignore

        active_app.get()
        return True
    except Exception:
        return False


class TelemetryPanel(Static):
    """Panel for displaying real-time telemetry data."""
    
    def compose(self) -> ComposeResult:
        """Compose telemetry widgets."""
        # Import widgets lazily so tests can patch `textual.widgets.*` symbols.
        from textual.widgets import Label, DataTable

        label = Label("📊 Telemetry", classes="panel-title")
        yield label
        if not _has_active_textual_app():
            return

        table = DataTable(id="telemetry-table")
        table.add_columns("Metric", "Value", "Unit", "Updated")
        # No-mocks: показываем схему метрик, но значения только N/A, пока не придёт реальная телеметрия.
        table.add_row("Position X", "N/A", "m", "—")
        table.add_row("Position Y", "N/A", "m", "—")
        table.add_row("Velocity", "N/A", "m/s", "—")
        table.add_row("Heading", "N/A", "deg", "—")
        table.add_row("Battery", "N/A", "%", "—")
        yield table


class RadarPanel(Static):
    """Panel for displaying radar tracks."""
    
    def compose(self) -> ComposeResult:
        """Compose radar widgets."""
        from textual.widgets import Label, DataTable

        label = Label("🎯 Radar Tracks", classes="panel-title")
        yield label
        if not _has_active_textual_app():
            return

        table = DataTable(id="radar-table")
        table.add_columns("Track ID", "Range", "Bearing", "Velocity", "Type")
        yield table


class ChatPanel(Static):
    """Panel for agent chat interaction."""
    
    def compose(self) -> ComposeResult:
        """Compose chat widgets."""
        from textual.widgets import Label, RichLog, Input, Button

        label = Label("💬 Agent Chat", classes="panel-title")
        yield label
        if not _has_active_textual_app():
            return

        yield Vertical(
            label,
            RichLog(id="chat-log", highlight=True, markup=True),
            Horizontal(
                Input(
                    placeholder="Type your message to Q-Agent...",
                    id="chat-input",
                ),
                Button("Send", variant="primary", id="send-button"),
                classes="chat-input-container",
            ),
        )


class CommandPanel(Static):
    """Panel for quick commands."""
    
    def compose(self) -> ComposeResult:
        """Compose command widgets."""
        from textual.widgets import Label, Button

        label = Label("⚡ Quick Commands", classes="panel-title")
        yield label
        if not _has_active_textual_app():
            return

        yield Vertical(
            Button("▶️ Start Simulation", id="cmd-start", variant="success"),
            Button("⏸️ Pause Simulation", id="cmd-pause", variant="warning"),
            Button("⏹️ Stop Simulation", id="cmd-stop", variant="error"),
            Button("🔄 Reset System", id="cmd-reset"),
            Button("📊 Export Telemetry", id="cmd-export"),
            Button("🔧 System Diagnostics", id="cmd-diagnostics"),
            classes="command-buttons",
        )


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
        self._latest_telemetry: dict = {}
        self._latest_event: dict = {}
        self.metrics_client = MetricsClient(max_points=500)
        
    def compose(self) -> ComposeResult:
        """Create the application layout."""
        # Import widgets lazily so tests can patch `textual.widgets.*` symbols.
        from textual.widgets import Header, Footer, Label, TabbedContent, TabPane

        yield Header()

        with TabbedContent(initial="telemetry"):
            yield TabPane(
                "📊 Telemetry",
                Horizontal(
                    Vertical(
                        TelemetryPanel(),
                        RadarPanel(),
                        classes="left-panel",
                    ),
                    Vertical(
                        CommandPanel(),
                        classes="right-panel",
                    ),
                )
                ,
                id="telemetry",
            )
            yield TabPane("🧩 Profile", ProfilePanel(), id="profile")
            yield TabPane("💬 Agent Chat", ChatPanel(), id="chat")
            yield TabPane("📈 Metrics", MetricsPanel(metrics_client=self.metrics_client), id="metrics")
            yield TabPane("⚙️ Settings", Label("Settings panel coming soon..."), id="settings")

        yield Footer()
    
    async def on_mount(self) -> None:
        """Handle mount event - initialize connections."""
        self.log("Operator Console started")
        self.log(f"NATS URL: {os.getenv('NATS_URL', 'not configured')}")
        self.log(
            "Q-Sim gRPC: "
            f"{os.getenv('QSIM_GRPC_HOST', os.getenv('GRPC_HOST', 'not configured'))}:"
            f"{os.getenv('QSIM_GRPC_PORT', os.getenv('GRPC_PORT', '50051'))}"
        )
        self.log(
            "Agent gRPC: "
            f"{os.getenv('AGENT_GRPC_HOST', 'not configured')}:"
            f"{os.getenv('AGENT_GRPC_PORT', '50052')}"
        )
        
        # Initialize clients
        await self.init_nats_client()
        await self.init_grpc_clients()
        # Start local metrics collection (real psutil metrics).
        try:
            await self.metrics_client.start_collection()
        except Exception as e:
            self.log(f"⚠️ Metrics collection unavailable: {e}")

    def log(self, message: str) -> None:  # type: ignore[override]
        """App-local logger (kept as a regular method for testability)."""
        try:
            print(message, flush=True)
        except Exception:
            pass
        
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

            # Subscribe to system telemetry (if published)
            try:
                await self.nats_client.subscribe_system_telemetry(self.handle_telemetry_data)
                self.log("📈 Subscribed to system telemetry")
            except Exception as e:
                self.log(f"⚠️ Telemetry subscription unavailable: {e}")

            # Subscribe to events (best-effort)
            try:
                await self.nats_client.subscribe_events(self.handle_event_data)
                self.log("🧾 Subscribed to events wildcard")
            except Exception as e:
                self.log(f"⚠️ Events subscription unavailable: {e}")

            # Subscribe to control responses (best-effort)
            try:
                await self.nats_client.subscribe_control_responses(self.handle_control_response)
                self.log("↩️ Subscribed to control responses")
            except Exception as e:
                self.log(f"⚠️ Control responses subscription unavailable: {e}")
            
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
        from textual.widgets import DataTable

        try:
            # Update radar table with new track data
            radar_table = self.query_one("#radar-table", DataTable)
            if radar_table:
                # Defensive: some DataTable.clear variants may drop columns in older Textual builds.
                if not getattr(radar_table, "columns", None):
                    try:
                        radar_table.add_columns("Track ID", "Range", "Bearing", "Velocity", "Type")
                    except Exception:
                        pass

                track_data = data.get("data", {}) if isinstance(data, dict) else {}
                if not isinstance(track_data, dict):
                    track_data = {}

                # Accept both historical demo keys and real RadarTrackModel keys.
                track_id = track_data.get("track_id") or track_data.get("id") or "N/A"
                range_m = track_data.get("range_m", track_data.get("range", "N/A"))
                bearing_deg = track_data.get("bearing_deg", track_data.get("bearing", "N/A"))
                vr_mps = track_data.get("vr_mps", track_data.get("velocity", "N/A"))
                obj_type = track_data.get("object_type") or track_data.get("type") or "Unknown"

                # Clear and update table (simplified for now)
                radar_table.clear()
                radar_table.add_row(
                    str(track_id),
                    str(range_m),
                    str(bearing_deg),
                    str(vr_mps),
                    str(obj_type),
                )
        except Exception as e:
            self.log(f"Error handling track data: {e}")

    async def handle_telemetry_data(self, data: dict) -> None:
        """Handle incoming telemetry data from NATS."""
        from textual.widgets import DataTable
        from pydantic import ValidationError

        from qiki.shared.models.telemetry import TelemetrySnapshotModel

        payload = data.get("data", {}) if isinstance(data, dict) else {}
        if isinstance(payload, dict):
            try:
                self._latest_telemetry = TelemetrySnapshotModel.normalize_payload(payload)
            except ValidationError as e:
                self.log(f"⚠️ Bad telemetry payload (ignored): {e}")
                return

        try:
            table = self.query_one("#telemetry-table", DataTable)
            if not table:
                return

            if not getattr(table, "columns", None):
                try:
                    table.add_columns("Metric", "Value", "Unit", "Updated")
                except Exception:
                    pass

            def _get(path: str, default: str = "N/A") -> str:
                cur: object = self._latest_telemetry
                for part in path.split("."):
                    if not isinstance(cur, dict) or part not in cur:
                        return default
                    cur = cur[part]
                return default if cur is None else str(cur)

            updated = datetime.now().strftime("%H:%M:%S")

            # Rebuild rows to avoid relying on DataTable row-key APIs.
            table.clear()
            table.add_row("Position X", _get("position.x"), "m", updated)
            table.add_row("Position Y", _get("position.y"), "m", updated)
            table.add_row("Position Z", _get("position.z"), "m", updated)
            table.add_row("Velocity", _get("velocity"), "m/s", updated)
            table.add_row("Heading", _get("heading"), "deg", updated)
            table.add_row("Battery", _get("battery"), "%", updated)
            table.add_row("Hull", _get("hull.integrity"), "%", updated)
            table.add_row("Radiation", _get("radiation_usvh"), "µSv/h", updated)
            table.add_row("Temp external", _get("temp_external_c"), "°C", updated)
            table.add_row("Temp core", _get("temp_core_c"), "°C", updated)
            table.add_row("Telemetry ts_unix_ms", _get("ts_unix_ms"), "ms", updated)
        except Exception as e:
            self.log(f"Error handling telemetry data: {e}")

    async def handle_event_data(self, data: dict) -> None:
        """Handle incoming events from NATS (best-effort logging)."""
        if isinstance(data, dict):
            self._latest_event = data
        subject = self._latest_event.get("subject") if isinstance(self._latest_event, dict) else None
        event_type = None
        if isinstance(self._latest_event, dict):
            payload = self._latest_event.get("data")
            if isinstance(payload, dict):
                event_type = payload.get("type") or payload.get("event_type")
        self.log(f"🧾 Event: {event_type or 'unknown'} ({subject or 'n/a'})")

    async def handle_control_response(self, data: dict) -> None:
        """Handle responses to control commands (FastStream bridge)."""
        payload = data.get("data", {}) if isinstance(data, dict) else {}
        if not isinstance(payload, dict):
            payload = {}
        success = payload.get("success")
        request_id = payload.get("requestId") or payload.get("request_id")
        message = None
        inner_payload = payload.get("payload")
        if isinstance(inner_payload, dict):
            message = inner_payload.get("status") or inner_payload.get("message")
        self.log(f"↩️ Control response: success={success} request={request_id} {message or ''}".strip())
        
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
        from textual.widgets import Input, RichLog

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

    def action_toggle_tab(self, tab_id: str) -> None:
        """Switch tabs by id (used by key bindings)."""
        try:
            tabs = self.query_one(TabbedContent)
        except Exception:
            return

        # Textual API changed across versions; try a couple of compatible paths.
        if hasattr(tabs, "active"):
            try:
                tabs.active = tab_id  # type: ignore[attr-defined]
                return
            except Exception:
                pass
        if hasattr(tabs, "show_tab"):
            try:
                tabs.show_tab(tab_id)  # type: ignore[attr-defined]
            except Exception:
                return
        
    async def execute_sim_command(self, command: str) -> None:
        """Execute a control command via NATS (no-mocks)."""
        if not self.nats_client:
            self.log(f"❌ Cannot execute {command}: NATS client not initialized")
            return

        from qiki.shared.models.core import CommandMessage, MessageMetadata
        from qiki.shared.nats_subjects import COMMANDS_CONTROL

        cmd = CommandMessage(
            command_name=f"sim.{command}",
            parameters={},
            metadata=MessageMetadata(
                message_type="control_command",
                source="operator_console",
                destination="faststream_bridge",
            ),
        )

        try:
            self.log(f"📤 Publishing command: sim.{command}")
            await self.nats_client.publish_command(
                COMMANDS_CONTROL,
                cmd.model_dump(mode="json"),
            )
            self.log("✅ Command published (waiting for response...)")
            return
        except Exception as e:
            self.log(f"❌ Error publishing command: {str(e)}")
    
    async def export_telemetry(self) -> None:
        """Export telemetry data."""
        self.log("📊 Exporting telemetry data...")
        try:
            if not self._latest_telemetry:
                self.log("⚠️ No telemetry received yet (nothing to export)")
                return

            from pathlib import Path

            export_dir = Path(os.getenv("QIKI_EXPORT_DIR", "/tmp/qiki_operator_console_exports"))
            export_dir.mkdir(parents=True, exist_ok=True)
            filename = f"telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            path = export_dir / filename
            path.write_text(
                json.dumps(self._latest_telemetry, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.log(f"✅ Telemetry exported to {path}")
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
    if os.getenv("ALLOW_LEGACY_OPERATOR_CONSOLE", "0").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        print(
            "LEGACY operator_console/main.py is archived. "
            "Use ORION (main_orion.py). "
            "To run anyway set ALLOW_LEGACY_OPERATOR_CONSOLE=1.",
            flush=True,
        )
        raise SystemExit(2)
    app = OperatorConsoleApp()
    app.run()


if __name__ == "__main__":
    main()
