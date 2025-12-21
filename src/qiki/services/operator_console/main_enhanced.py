#!/usr/bin/env python3
"""
QIKI Operator Console - Enhanced Version.

Complete console with charts, metrics history, and data export.
"""

import asyncio
from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional, Deque, List
import sys
import uuid

from rich.table import Table
from rich.live import Live
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from clients.nats_realtime_client import RealtimeNATSClient, RadarFrame
from clients.grpc_client import QSimGrpcClient, QAgentGrpcClient, SimulationCommand
from ui.charts import MetricsHistory, MetricsPanel, BatteryIndicator, RadarVisualization
from utils.data_export import DataExporter, DataLogger


class SignalStrength:
    """Utility for rendering signal strength as text."""

    @staticmethod
    def render(value: int) -> str:
        if value >= 80:
            style = "bold green"
        elif value >= 50:
            style = "yellow"
        else:
            style = "red"
        return f"[{style}]{value}%[/]"


console = Console()


class QIKIOperatorConsoleEnhanced:
    """Enhanced operator console with full features."""
    
    def __init__(self):
        """Initialize the console."""
        self.session_id = str(uuid.uuid4())[:8]
        self.nats_client: Optional[RealtimeNATSClient] = None
        self.grpc_sim_client: Optional[QSimGrpcClient] = None
        self.grpc_agent_client: Optional[QAgentGrpcClient] = None
        self.running = False
        
        # Data buffers
        self.telemetry_buffer: Dict[str, Any] = {}
        self.radar_frames_buffer: Deque[Dict[str, Any]] = deque(maxlen=100)
        self.events_buffer: Deque[Dict[str, Any]] = deque(maxlen=50)
        self.chat_history: Deque[Dict[str, Any]] = deque(maxlen=50)
        self.command_history: Deque[Dict[str, Any]] = deque(maxlen=50)
        
        # Metrics history for visualization
        self.metrics_history = MetricsHistory(max_points=100)
        
        # Data export and logging
        self.data_exporter = DataExporter("/app/exports")
        self.data_logger = DataLogger("/app/logs")
        
        # Statistics
        self.stats: Dict[str, Any] = {
            "frames_received": 0,
            "events_received": 0,
            "commands_sent": 0,
            "exports_created": 0,
            "uptime_start": datetime.now(),
            "last_frame_time": None
        }
        
    async def initialize(self):
        """Initialize all connections."""
        tasks = []
        
        # Initialize NATS
        self.nats_client = RealtimeNATSClient()
        tasks.append(self.init_nats())
        
        # Initialize gRPC clients
        self.grpc_sim_client = QSimGrpcClient()
        self.grpc_agent_client = QAgentGrpcClient()
        tasks.append(self.init_grpc())
        
        # Run all initializations
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                console.print(f"[red]Initialization error: {result}[/red]")
                
    async def init_nats(self):
        """Initialize NATS connection."""
        if self.nats_client:
            await self.nats_client.connect()
            
            # Register callbacks
            self.nats_client.register_callback("radar_frames", self.on_radar_frame)
            self.nats_client.register_callback("telemetry", self.on_telemetry)
            self.nats_client.register_callback("events", self.on_event)
            
            # Subscribe to streams
            await self.nats_client.subscribe_all()
        
    async def init_grpc(self):
        """Initialize gRPC connections."""
        if self.grpc_sim_client:
            await self.grpc_sim_client.connect()
        if self.grpc_agent_client:
            await self.grpc_agent_client.connect()
            
    async def on_radar_frame(self, frame: RadarFrame):
        """Handle incoming radar frame."""
        self.stats["frames_received"] += 1
        self.stats["last_frame_time"] = datetime.now()
        
        frame_data = {
            "timestamp": frame.timestamp,
            "frame_id": frame.frame_id,
            "sensor_id": frame.sensor_id,
            "detections": len(frame.detections),
            "details": frame.detections[:5]
        }
        
        self.radar_frames_buffer.append(frame_data)
        
        # Log frame
        self.data_logger.log_radar_frame(frame_data)
        
        # Update metrics history
        self.metrics_history.add_metric("radar_detections", len(frame.detections))
        
    async def on_telemetry(self, data: dict):
        """Handle telemetry update."""
        self.telemetry_buffer = data
        
        # Update metrics history
        if "position_x" in data:
            self.metrics_history.add_metric("Position X", data["position_x"])
        if "position_y" in data:
            self.metrics_history.add_metric("Position Y", data["position_y"])
        if "velocity" in data:
            self.metrics_history.add_metric("Velocity", data["velocity"])
        if "battery" in data:
            self.metrics_history.add_metric("Battery", data["battery"])
            
        # Log telemetry
        self.data_logger.log_telemetry(data)
        
    async def on_event(self, event: dict):
        """Handle system event."""
        self.stats["events_received"] += 1
        self.events_buffer.append(event)
        
        # Log event
        self.data_logger.log_event(event)
        
    async def handle_command(self, command: str):
        """Handle user command."""
        self.stats["commands_sent"] += 1
        self.command_history.append({
            "command": command,
            "timestamp": datetime.now()
        })
        
        if not self.grpc_sim_client or not self.grpc_agent_client:
            return "gRPC clients are not initialized"

        sim_client = self.grpc_sim_client
        agent_client = self.grpc_agent_client

        cmd_lower = command.lower().strip()
        
        # Export commands
        if cmd_lower.startswith("export"):
            return await self.handle_export_command(cmd_lower)
            
        # Simulation commands
        elif cmd_lower == "start":
            result = await sim_client.send_command(SimulationCommand.START)
            return result.get("message", "Command sent")
            
        elif cmd_lower == "stop":
            result = await sim_client.send_command(SimulationCommand.STOP)
            return result.get("message", "Command sent")
            
        elif cmd_lower == "pause":
            result = await sim_client.send_command(SimulationCommand.PAUSE)
            return result.get("message", "Command sent")
            
        elif cmd_lower == "resume":
            result = await sim_client.send_command(SimulationCommand.RESUME)
            return result.get("message", "Command sent")
            
        elif cmd_lower == "reset":
            result = await sim_client.send_command(SimulationCommand.RESET)
            # Clear metrics history on reset
            self.metrics_history = MetricsHistory(max_points=100)
            return result.get("message", "Command sent")
            
        elif cmd_lower.startswith("speed "):
            try:
                speed = float(cmd_lower.split()[1])
                result = await sim_client.set_simulation_speed(speed)
                return result.get("message", "Speed updated")
            except ValueError:
                return "Invalid speed value"
                
        elif cmd_lower == "status":
            sim_state = sim_client.get_simulation_state()
            fsm_state = await agent_client.get_fsm_state()
            return f"Sim: {'Running' if sim_state['running'] else 'Stopped'} | FSM: {fsm_state['current_state']}"
            
        elif cmd_lower == "help":
            return ("Commands: start, stop, pause, resume, reset, speed <value>, status, "
                   "chat <message>, export [telemetry|radar|events|session] [json|csv]")
            
        elif cmd_lower.startswith("chat "):
            message = command[5:]
            response = await agent_client.send_message(message)
            self.chat_history.append({
                "role": "user",
                "message": message,
                "timestamp": datetime.now()
            })
            self.chat_history.append({
                "role": "agent",
                "message": response,
                "timestamp": datetime.now()
            })
            return f"Agent: {response}"
            
        else:
            return f"Unknown command: {command}. Type 'help' for available commands."
            
    async def handle_export_command(self, cmd: str):
        """Handle export commands."""
        parts = cmd.split()
        
        if len(parts) < 2:
            return "Usage: export [telemetry|radar|events|session] [json|csv]"
            
        export_type = parts[1] if len(parts) > 1 else "session"
        export_format = parts[2] if len(parts) > 2 else "json"
        
        try:
            if export_type == "telemetry":
                path = self.data_exporter.export_telemetry(self.telemetry_buffer, export_format)
            elif export_type == "radar":
                path = self.data_exporter.export_radar_frames(self.radar_frames_buffer, export_format)
            elif export_type == "events":
                path = self.data_exporter.export_events(self.events_buffer, export_format)
            elif export_type == "session":
                session_data = self.get_session_data()
                path = self.data_exporter.export_full_session(session_data)
            else:
                return f"Unknown export type: {export_type}"
                
            self.stats["exports_created"] += 1
            return f"✅ Exported to: {path}"
            
        except Exception as e:
            return f"❌ Export failed: {e}"
            
    def get_session_data(self) -> Dict[str, Any]:
        """Get complete session data."""
        uptime = 0
        start_time = self.stats.get("uptime_start")
        if isinstance(start_time, datetime):
            uptime = (datetime.now() - start_time).seconds
            
        return {
            "session_id": self.session_id,
            "uptime_seconds": uptime,
            "stats": self.stats.copy(),
            "telemetry_buffer": self.telemetry_buffer,
            "radar_frames_buffer": self.radar_frames_buffer,
            "events_buffer": self.events_buffer,
            "command_history": self.command_history,
            "chat_history": self.chat_history
        }
    
    def create_metrics_panel(self) -> Panel:
        """Create metrics panel with sparklines."""
        metrics_panel = MetricsPanel(self.metrics_history, title="📈 Metrics History")
        return metrics_panel.create_panel()
    
    def create_telemetry_panel(self) -> Panel:
        """Create enhanced telemetry panel."""
        table = Table(show_header=False, expand=True)
        table.add_column("", style="cyan", no_wrap=True)
        table.add_column("", style="white")
        
        if self.telemetry_buffer:
            tel = self.telemetry_buffer
            
            # Position with sparkline
            pos_x = tel.get('position_x', 0)
            pos_y = tel.get('position_y', 0)
            pos_spark = self.metrics_history.get_sparkline("Position X", width=15)
            table.add_row("Position", f"X: {pos_x:.2f}m, Y: {pos_y:.2f}m  {pos_spark}")
            
            # Velocity with sparkline
            velocity = tel.get('velocity', 0)
            vel_spark = self.metrics_history.get_sparkline("Velocity", width=15)
            table.add_row("Velocity", f"{velocity:.1f} m/s  {vel_spark}")
            
            # Battery with indicator
            battery = tel.get('battery', 100)
            battery_text = BatteryIndicator.render(battery, width=10)
            table.add_row("Battery", battery_text)
            
            # Signal strength
            signal = tel.get('signal', 75)
            signal_text = SignalStrength.render(signal)
            table.add_row("Signal", signal_text)
        else:
            table.add_row("Status", "Waiting for telemetry...")
        
        # Add simulation state
        if self.grpc_sim_client:
            sim_state = self.grpc_sim_client.get_simulation_state()
            status = "🟢 Running" if sim_state["running"] else "🔴 Stopped"
            if sim_state["paused"]:
                status = "⏸️ Paused"
            table.add_row("Simulation", f"{status} ({sim_state['speed']}x speed)")
        
        # Add statistics
        table.add_row("─" * 20, "─" * 40)
        table.add_row("Statistics", f"F: {self.stats['frames_received']} | "
                                   f"E: {self.stats['events_received']} | "
                                   f"C: {self.stats['commands_sent']}")
        
        return Panel(table, title="📊 System Telemetry", border_style="cyan")
    
    def create_radar_panel(self) -> Panel:
        """Create radar visualization panel."""
        # Get latest detections
        detections = []
        for frame in list(self.radar_frames_buffer)[-5:]:
            for det in frame.get("details", []):
                if isinstance(det, dict) and "range" in det and "bearing" in det:
                    detections.append(det)
        
        # Create ASCII radar visualization
        radar_viz = RadarVisualization(width=30, height=15)
        radar_display = radar_viz.render(detections)
        
        # Add frame counter
        radar_text = Text()
        radar_text.append(f"Frames: {len(self.radar_frames_buffer)}\n", style="yellow")
        radar_text.append(f"Detections: {len(detections)}\n\n", style="cyan")
        radar_text.append(radar_display, style="green")
        
        return Panel(radar_text, title="🎯 Radar Visualization", border_style="green")
    
    def create_layout(self) -> Layout:
        """Create the enhanced layout."""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=1)
        )
        
        # Header
        header_text = Align.center(
            Text(f"QIKI OPERATOR CONSOLE ENHANCED | Session: {self.session_id}", 
                 style="bold white on blue"),
            vertical="middle"
        )
        layout["header"].update(Panel(header_text, style="bold blue"))
        
        # Body - three columns
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="center", ratio=1),
            Layout(name="right", ratio=1)
        )
        
        # Left column
        layout["left"].split_column(
            Layout(name="telemetry", size=12),
            Layout(name="commands")
        )
        
        # Center column
        layout["center"].split_column(
            Layout(name="metrics", size=12),
            Layout(name="events")
        )
        
        # Right column
        layout["right"].split_column(
            Layout(name="radar", size=20),
            Layout(name="chat")
        )
        
        return layout
    
    def create_events_panel(self) -> Panel:
        """Create events panel."""
        events_text = Text()
        
        for event in list(self.events_buffer)[-8:]:
            severity = event.get("severity", "info")
            color = {"error": "red", "warning": "yellow", "info": "cyan"}.get(severity, "white")
            
            time_str = event.get("timestamp", "")[:19]
            events_text.append(f"[{time_str}] ", style="dim")
            events_text.append(f"{event.get('type', 'EVENT')}: ", style=f"bold {color}")
            events_text.append(f"{event.get('message', '')}\n", style=color)
        
        if not self.events_buffer:
            events_text.append("No events yet...", style="dim")
        
        return Panel(events_text, title=f"⚡ Events ({len(self.events_buffer)})", 
                    border_style="yellow")
    
    def create_commands_panel(self) -> Panel:
        """Create commands panel."""
        cmd_text = Text()
        
        # Recent commands
        cmd_text.append("Recent:\n", style="bold")
        for cmd in list(self.command_history)[-3:]:
            time_str = cmd["timestamp"].strftime("%H:%M:%S")
            cmd_text.append(f"[{time_str}] {cmd['command']}\n", style="cyan")
        
        cmd_text.append("\n📌 Commands:\n", style="bold yellow")
        cmd_text.append("• start/stop/pause/reset\n", style="green")
        cmd_text.append("• speed <n>\n", style="green")
        cmd_text.append("• export <type> [format]\n", style="green")
        cmd_text.append("• chat <message>\n", style="green")
        
        return Panel(cmd_text, title="🎮 Commands", border_style="blue")
    
    def create_chat_panel(self) -> Panel:
        """Create chat panel."""
        chat_text = Text()
        
        for msg in list(self.chat_history)[-6:]:
            time_str = msg["timestamp"].strftime("%H:%M")
            if msg["role"] == "user":
                chat_text.append(f"[{time_str}] You: ", style="cyan")
                chat_text.append(f"{msg['message']}\n", style="white")
            else:
                chat_text.append(f"[{time_str}] AI: ", style="green")
                chat_text.append(f"{msg['message']}\n", style="bright_white")
        
        if not self.chat_history:
            chat_text.append("Use 'chat <message>' to talk", style="dim")
        
        return Panel(chat_text, title="💬 Chat", border_style="green")
    
    async def run(self):
        """Main application loop."""
        console.print(
            "\n[bold cyan]Starting QIKI Operator Console Enhanced "
            f"(Session: {self.session_id})...[/bold cyan]\n"
        )
        
        try:
            # Initialize connections
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Initializing...", total=None)
                await self.initialize()
                progress.update(task, completed=100, description="✅ Ready!")
            
            self.running = True
            
            # Main display loop
            with Live(self.create_layout(), refresh_per_second=2, screen=True) as live:
                while self.running:
                    layout = self.create_layout()
                    
                    # Update all panels
                    layout["telemetry"].update(self.create_telemetry_panel())
                    layout["metrics"].update(self.create_metrics_panel())
                    layout["radar"].update(self.create_radar_panel())
                    layout["events"].update(self.create_events_panel())
                    layout["commands"].update(self.create_commands_panel())
                    layout["chat"].update(self.create_chat_panel())
                    
                    # Footer
                    uptime = 0
                    start_time = self.stats.get("uptime_start")
                    if isinstance(start_time, datetime):
                        uptime = (datetime.now() - start_time).seconds
                        
                    footer_text = Align.center(
                        Text(f"Uptime: {uptime//60}m | Frames: {self.stats['frames_received']} | "
                             f"Events: {self.stats['events_received']} | Exports: {self.stats['exports_created']}", 
                             style="dim"),
                        vertical="middle"
                    )
                    layout["footer"].update(footer_text)
                    
                    live.update(layout)
                    await asyncio.sleep(0.5)
                    
        except KeyboardInterrupt:
            console.print("\n[bold red]Console terminated.[/bold red]")
            
            # Create final report
            session_data = self.get_session_data()
            report = self.data_exporter.create_report(session_data)
            console.print("\n[bold cyan]Session Report:[/bold cyan]")
            console.print(report)
            
            # Export session data
            try:
                export_path = self.data_exporter.export_full_session(session_data)
                console.print(f"\n[green]Session data exported to: {export_path}[/green]")
            except Exception as e:
                console.print(f"\n[red]Failed to export session: {e}[/red]")
                
        except Exception as e:
            console.print(f"\n[bold red]Error: {e}[/bold red]")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False
            if self.nats_client:
                await self.nats_client.disconnect()
            if self.grpc_sim_client:
                await self.grpc_sim_client.disconnect()
            console.print("[dim]Cleanup complete.[/dim]")


async def main():
    """Entry point."""
    console_app = QIKIOperatorConsoleEnhanced()
    
    if len(sys.argv) > 1:
        # Command line mode
        command = " ".join(sys.argv[1:])
        await console_app.initialize()
        result = await console_app.handle_command(command)
        console.print(result)
    else:
        # Interactive mode
        await console_app.run()


if __name__ == "__main__":
    asyncio.run(main())
