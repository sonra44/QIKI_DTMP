#!/usr/bin/env python3
"""
QIKI Operator Console - Integrated Version with Real Data.

Terminal UI with real NATS data streams integration.
"""

import asyncio
from collections import deque
from datetime import datetime
from typing import Optional, Dict, Any, Deque, List

from rich.table import Table
from rich.live import Live
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from clients.nats_realtime_client import RealtimeNATSClient, RadarFrame


console = Console()


class QIKIOperatorConsole:
    """Main operator console application with real data integration."""

    def __init__(self):
        """Initialize the console."""
        self.nats_client: Optional[RealtimeNATSClient] = None
        self.running = False

        # Data buffers
        self.telemetry_buffer: Dict[str, Any] = {}
        self.radar_frames_buffer: Deque[Dict[str, Any]] = deque(maxlen=50)
        self.events_buffer: Deque[Dict[str, Any]] = deque(maxlen=20)
        self.tracks_buffer: List[Any] = []

        # Statistics
        self.stats: Dict[str, Any] = {
            "frames_received": 0,
            "events_received": 0,
            "uptime_start": datetime.now(),
            "last_frame_time": None,
        }

    async def initialize(self):
        """Initialize NATS connection and subscriptions."""
        self.nats_client = RealtimeNATSClient()

        # Connect to NATS
        await self.nats_client.connect()

        # Register callbacks
        self.nats_client.register_callback("radar_frames", self.on_radar_frame)
        self.nats_client.register_callback("telemetry", self.on_telemetry)
        self.nats_client.register_callback("events", self.on_event)

        # Subscribe to streams
        await self.nats_client.subscribe_all()

    async def on_radar_frame(self, frame: RadarFrame):
        """Handle incoming radar frame."""
        self.stats["frames_received"] += 1
        self.stats["last_frame_time"] = datetime.now()

        # Add to buffer
        self.radar_frames_buffer.append(
            {
                "timestamp": frame.timestamp,
                "frame_id": frame.frame_id,
                "sensor_id": frame.sensor_id,
                "detections": len(frame.detections),
                "details": frame.detections[:5],  # Keep first 5 detections for display
            }
        )

    async def on_telemetry(self, data: dict):
        """Handle telemetry update."""
        self.telemetry_buffer = data

    async def on_event(self, event: dict):
        """Handle system event."""
        self.stats["events_received"] += 1
        self.events_buffer.append(event)

    @staticmethod
    def _telemetry_soc_pct(tel: Dict[str, Any]) -> float:
        """Return canonical SoC with legacy compatibility fallback."""
        raw = tel.get("soc_pct", tel.get("battery", 100))
        try:
            return float(raw)
        except Exception:
            return 100.0

    def create_telemetry_table(self) -> Table:
        """Create telemetry display table with real data."""
        table = Table(title="📊 System Telemetry", expand=True)
        table.add_column("Parameter", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        table.add_column("Status", style="yellow")

        # Use real telemetry data if available
        if self.telemetry_buffer:
            tel = self.telemetry_buffer
            table.add_row("Position X", f"{tel.get('position_x', 0):.2f} m", "🟢")
            table.add_row("Position Y", f"{tel.get('position_y', 0):.2f} m", "🟢")
            table.add_row("Velocity", f"{tel.get('velocity', 0):.1f} m/s", "🟢")
            table.add_row("Heading", f"{tel.get('heading', 0):.1f}°", "🟢")
            soc_pct = self._telemetry_soc_pct(tel)
            table.add_row("Battery", f"{soc_pct:.1f}%", "🟢" if soc_pct > 30 else "🟡")
        else:
            table.add_row("Waiting for telemetry...", "-", "⏳")

        # Add statistics
        table.add_row("─" * 15, "─" * 15, "─" * 5)
        table.add_row("Frames Received", str(self.stats["frames_received"]), "📡")
        table.add_row("Events", str(self.stats["events_received"]), "⚡")

        start_time = self.stats.get("uptime_start")
        if isinstance(start_time, datetime):
            uptime = datetime.now() - start_time
            table.add_row("Uptime", f"{uptime.seconds // 60}m {uptime.seconds % 60}s", "⏱️")
        else:
            table.add_row("Uptime", "N/A", "⏱️")

        return table

    def create_radar_table(self) -> Table:
        """Create radar display with real frame data."""
        table = Table(title="🎯 Radar Frames & Detections", expand=True)
        table.add_column("Frame ID", style="yellow", no_wrap=True)
        table.add_column("Sensor", style="cyan")
        table.add_column("Detections", style="magenta")
        table.add_column("Time", style="dim")

        # Show last 10 frames
        for frame_data in list(self.radar_frames_buffer)[-10:]:
            time_str = frame_data["timestamp"].strftime("%H:%M:%S")
            table.add_row(
                frame_data["frame_id"][:8] + "...",
                frame_data["sensor_id"][:8] + "...",
                str(frame_data["detections"]),
                time_str,
            )

        if not self.radar_frames_buffer:
            table.add_row("Waiting for radar data...", "-", "-", "-")

        return table

    def create_events_panel(self) -> Panel:
        """Create events panel showing system events."""
        events_text = Text()

        if self.events_buffer:
            for event in list(self.events_buffer)[-10:]:
                severity_color = {"error": "red", "warning": "yellow", "info": "cyan", "debug": "dim"}.get(
                    event.get("severity", "info"), "white"
                )

                events_text.append(f"[{event.get('timestamp', 'N/A')[:19]}] ", style="dim")
                events_text.append(f"{event.get('type', 'UNKNOWN')}: ", style=f"bold {severity_color}")
                events_text.append(f"{event.get('message', '')}\n", style=severity_color)
        else:
            events_text.append("No events yet...\n", style="dim")

        return Panel(events_text, title=f"⚡ System Events ({len(self.events_buffer)})", border_style="blue")

    def create_status_panel(self) -> Panel:
        """Create system status panel."""
        status_text = Text()

        # NATS Status
        status_text.append("NATS: ", style="bold")
        if self.nats_client and self.nats_client.nc and not self.nats_client.nc.is_closed:
            status_text.append("✅ Connected\n", style="green")
            status_text.append(f"  URL: {self.nats_client.url}\n", style="dim")

            # Latest data status
            last_frame = self.stats.get("last_frame_time")
            if isinstance(last_frame, datetime):
                time_since = (datetime.now() - last_frame).seconds
                if time_since < 5:
                    status_text.append("\nData Flow: ", style="bold")
                    status_text.append("🟢 Active\n", style="green bold")
                else:
                    status_text.append("\nData Flow: ", style="bold")
                    status_text.append(f"🟡 Idle ({time_since}s)\n", style="yellow")
        else:
            status_text.append("❌ Disconnected\n", style="red")

        # Simulation Status
        status_text.append("\nSimulation: ", style="bold")
        status_text.append("▶️ Running\n", style="cyan bold")

        # Frame Rate
        start_time = self.stats.get("uptime_start")
        if self.stats["frames_received"] > 0 and isinstance(start_time, datetime):
            uptime_seconds = (datetime.now() - start_time).seconds
            if uptime_seconds > 0:
                fps = self.stats["frames_received"] / uptime_seconds
                status_text.append(f"\nFrame Rate: {fps:.1f} fps\n", style="dim")

        return Panel(status_text, title="🔧 System Status", border_style="blue")

    def create_command_hints(self) -> Panel:
        """Create command hints panel."""
        hints = Text()
        hints.append("📌 Commands:\n\n", style="bold yellow")

        commands = [
            ("Ctrl+C", "Exit"),
            ("S", "Start/Stop"),
            ("R", "Reset"),
            ("E", "Export Data"),
            ("C", "Clear Buffers"),
            ("H", "Help"),
        ]

        for key, desc in commands:
            hints.append(key, style="bold cyan")
            hints.append(f" - {desc}\n")

        return Panel(hints, title="⌨️ Controls", border_style="yellow")

    def create_layout(self) -> Layout:
        """Create the main layout."""
        layout = Layout()

        # Split into header, body, and footer
        layout.split_column(Layout(name="header", size=3), Layout(name="body"), Layout(name="footer", size=1))

        # Header
        header_text = Align.center(
            Text("QIKI OPERATOR CONSOLE - LIVE DATA", style="bold white on blue"), vertical="middle"
        )
        layout["header"].update(Panel(header_text, style="bold blue"))

        # Body - split into left and right
        layout["body"].split_row(Layout(name="left", ratio=2), Layout(name="right", ratio=1))

        # Left side - telemetry, radar, and events
        layout["left"].split_column(
            Layout(name="telemetry", size=12), Layout(name="radar", size=12), Layout(name="events")
        )

        # Right side - status and commands
        layout["right"].split_column(Layout(name="status", size=12), Layout(name="commands"))

        # Footer
        footer_text = Align.center(
            Text(
                "Connected to QIKI Digital Twin | "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                f"Frames: {self.stats['frames_received']}",
                style="dim",
            ),
            vertical="middle",
        )
        layout["footer"].update(footer_text)

        return layout

    async def run(self):
        """Main application loop."""
        console.print("\n[bold cyan]Starting QIKI Operator Console with Live Data...[/bold cyan]\n")

        try:
            # Initialize NATS connection
            with Progress(
                SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
            ) as progress:
                task = progress.add_task("Connecting to NATS...", total=None)
                await self.initialize()
                progress.update(task, completed=100, description="✅ Connected!")

            self.running = True

            # Main display loop
            with Live(self.create_layout(), refresh_per_second=2, screen=True) as live:
                while self.running:
                    # Update layout with fresh data
                    layout = self.create_layout()
                    layout["telemetry"].update(self.create_telemetry_table())
                    layout["radar"].update(self.create_radar_table())
                    layout["events"].update(self.create_events_panel())
                    layout["status"].update(self.create_status_panel())
                    layout["commands"].update(self.create_command_hints())

                    # Update footer
                    footer_text = Align.center(
                        Text(
                            "Connected to QIKI | "
                            f"{datetime.now().strftime('%H:%M:%S')} | "
                            f"Frames: {self.stats['frames_received']} | "
                            f"Events: {self.stats['events_received']}",
                            style="dim",
                        ),
                        vertical="middle",
                    )
                    layout["footer"].update(footer_text)

                    live.update(layout)
                    await asyncio.sleep(0.5)

        except KeyboardInterrupt:
            console.print("\n[bold red]Console terminated by user.[/bold red]")
        except Exception as e:
            console.print(f"\n[bold red]Error: {e}[/bold red]")
            import traceback

            traceback.print_exc()
        finally:
            if self.nats_client:
                await self.nats_client.disconnect()
            console.print("[dim]Cleanup complete.[/dim]")


async def main():
    """Entry point."""
    console_app = QIKIOperatorConsole()
    await console_app.run()


if __name__ == "__main__":
    asyncio.run(main())
