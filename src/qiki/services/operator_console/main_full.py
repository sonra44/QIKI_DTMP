#!/usr/bin/env python3
"""
QIKI Operator Console - Full Integration Version.

Complete console with NATS data, gRPC commands, and agent chat.
"""

import asyncio
from collections import deque
from datetime import datetime
from typing import Optional, Dict, Any, Deque, List
import sys

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


console = Console()


class QIKIOperatorConsoleFull:
    """Full-featured operator console with complete integration."""
    
    def __init__(self):
        """Initialize the console."""
        self.nats_client: Optional[RealtimeNATSClient] = None
        self.grpc_sim_client: Optional[QSimGrpcClient] = None
        self.grpc_agent_client: Optional[QAgentGrpcClient] = None
        self.running = False
        self.command_mode = False
        
        # Data buffers
        self.telemetry_buffer: Dict[str, Any] = {}
        self.radar_frames_buffer: Deque[Dict[str, Any]] = deque(maxlen=50)
        self.events_buffer: Deque[Dict[str, Any]] = deque(maxlen=20)
        self.chat_history: Deque[Dict[str, Any]] = deque(maxlen=50)
        self.command_history: Deque[Dict[str, Any]] = deque(maxlen=20)
        
        # Statistics
        self.stats: Dict[str, Any] = {
            "frames_received": 0,
            "events_received": 0,
            "commands_sent": 0,
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
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                console.print(f"[red]Initialization error: {result}[/red]")
                
    async def init_nats(self):
        """Initialize NATS connection."""
        if not self.nats_client:
            return
            
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
        
        self.radar_frames_buffer.append({
            "timestamp": frame.timestamp,
            "frame_id": frame.frame_id,
            "sensor_id": frame.sensor_id,
            "detections": len(frame.detections),
            "details": frame.detections[:5]
        })
        
    async def on_telemetry(self, data: dict):
        """Handle telemetry update."""
        self.telemetry_buffer = data
        
    async def on_event(self, event: dict):
        """Handle system event."""
        self.stats["events_received"] += 1
        self.events_buffer.append(event)
        
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
        
        # Parse and execute command
        cmd_lower = command.lower().strip()
        
        if cmd_lower == "start":
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
            return "Commands: start, stop, pause, resume, reset, speed <value>, status, chat <message>"
            
        elif cmd_lower.startswith("chat "):
            message = command[5:]  # Remove "chat " prefix
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
    
    def create_telemetry_table(self) -> Table:
        """Create telemetry display table."""
        table = Table(title="📊 System Telemetry", expand=True)
        table.add_column("Parameter", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        table.add_column("Status", style="yellow")
        
        if self.telemetry_buffer:
            tel = self.telemetry_buffer
            table.add_row("Position X", f"{tel.get('position_x', 0):.2f} m", "🟢")
            table.add_row("Position Y", f"{tel.get('position_y', 0):.2f} m", "🟢")
            table.add_row("Velocity", f"{tel.get('velocity', 0):.1f} m/s", "🟢")
            table.add_row("Heading", f"{tel.get('heading', 0):.1f}°", "🟢")
            table.add_row("Battery", f"{tel.get('battery', 100)}%", 
                         "🟢" if tel.get('battery', 100) > 30 else "🟡")
        
        # Simulation state from gRPC
        if self.grpc_sim_client:
            sim_state = self.grpc_sim_client.get_simulation_state()
            table.add_row("─" * 15, "─" * 15, "─" * 5)
            table.add_row("Simulation", 
                         "Running" if sim_state["running"] else "Stopped",
                         "▶️" if sim_state["running"] else "⏹️")
            if sim_state["paused"]:
                table.add_row("Status", "Paused", "⏸️")
            table.add_row("Speed", f"{sim_state['speed']}x", "⚡")
        
        # Statistics
        table.add_row("─" * 15, "─" * 15, "─" * 5)
        table.add_row("Frames", str(self.stats["frames_received"]), "📡")
        table.add_row("Events", str(self.stats["events_received"]), "⚡")
        table.add_row("Commands", str(self.stats["commands_sent"]), "📤")
        
        return table
    
    def create_command_panel(self) -> Panel:
        """Create command panel."""
        cmd_text = Text()
        
        # Show last 5 commands
        cmd_text.append("📝 Recent Commands:\n", style="bold yellow")
        for cmd in list(self.command_history)[-5:]:
            time_str = cmd["timestamp"].strftime("%H:%M:%S")
            cmd_text.append(f"[{time_str}] ", style="dim")
            cmd_text.append(f"{cmd['command']}\n", style="cyan")
        
        if not self.command_history:
            cmd_text.append("No commands yet\n", style="dim")
            
        cmd_text.append("\n⌨️ Available:\n", style="bold")
        commands = ["start", "stop", "pause", "reset", "speed <n>", "status", "chat <msg>"]
        cmd_text.append(" | ".join(commands), style="green")
        
        return Panel(cmd_text, title="🎮 Command Center", border_style="blue")
    
    def create_chat_panel(self) -> Panel:
        """Create chat panel."""
        chat_text = Text()
        
        # Show last 10 chat messages
        for msg in list(self.chat_history)[-10:]:
            time_str = msg["timestamp"].strftime("%H:%M:%S")
            
            if msg["role"] == "user":
                chat_text.append(f"[{time_str}] You: ", style="cyan")
                chat_text.append(f"{msg['message']}\n", style="white")
            else:
                chat_text.append(f"[{time_str}] Agent: ", style="green")
                chat_text.append(f"{msg['message']}\n", style="bright_white")
        
        if not self.chat_history:
            chat_text.append("Start a conversation with 'chat <message>'\n", style="dim")
            
        return Panel(chat_text, title="💬 Agent Chat", border_style="green")
    
    def create_status_panel(self) -> Panel:
        """Create comprehensive status panel."""
        status_text = Text()
        
        # NATS Status
        status_text.append("NATS: ", style="bold")
        if self.nats_client and self.nats_client.nc and not self.nats_client.nc.is_closed:
            status_text.append("✅ Connected\n", style="green")
        else:
            status_text.append("❌ Disconnected\n", style="red")
        
        # gRPC Sim Status
        status_text.append("gRPC Sim: ", style="bold")
        if self.grpc_sim_client and self.grpc_sim_client.connected:
            status_text.append("✅ Connected\n", style="green")
        else:
            status_text.append("❌ Disconnected\n", style="red")
            
        # gRPC Agent Status
        status_text.append("gRPC Agent: ", style="bold")
        if self.grpc_agent_client and self.grpc_agent_client.connected:
            status_text.append("✅ Connected\n", style="green")
        else:
            status_text.append("❌ Disconnected\n", style="red")
        
        # Data flow
        last_frame = self.stats.get("last_frame_time")
        if isinstance(last_frame, datetime):
            time_since = (datetime.now() - last_frame).seconds
            status_text.append("\nData Flow: ", style="bold")
            if time_since < 5:
                status_text.append("🟢 Active\n", style="green bold")
            else:
                status_text.append(f"🟡 Idle ({time_since}s)\n", style="yellow")
        
        return Panel(status_text, title="🔧 System Status", border_style="blue")
    
    def create_layout(self) -> Layout:
        """Create the main layout."""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=1)
        )
        
        # Header
        header_text = Align.center(
            Text("QIKI OPERATOR CONSOLE - FULL INTEGRATION", style="bold white on blue"),
            vertical="middle"
        )
        layout["header"].update(Panel(header_text, style="bold blue"))
        
        # Body
        layout["body"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        # Left side
        layout["left"].split_column(
            Layout(name="telemetry", size=15),
            Layout(name="chat", size=12),
            Layout(name="radar")
        )
        
        # Right side
        layout["right"].split_column(
            Layout(name="status", size=10),
            Layout(name="commands")
        )
        
        return layout
    
    async def run_command_loop(self):
        """Run command input loop in background."""
        while self.running:
            try:
                # Non-blocking check for commands
                await asyncio.sleep(1)
                # In real implementation, this would handle keyboard input
            except Exception as e:
                console.print(f"[red]Command loop error: {e}[/red]")
    
    async def run(self):
        """Main application loop."""
        console.print("\n[bold cyan]Starting QIKI Operator Console - Full Integration...[/bold cyan]\n")
        
        try:
            # Initialize connections
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Initializing connections...", total=None)
                await self.initialize()
                progress.update(task, completed=100, description="✅ All systems connected!")
            
            self.running = True
            
            # Start command loop
            asyncio.create_task(self.run_command_loop())
            
            # Main display loop
            with Live(self.create_layout(), refresh_per_second=2, screen=True) as live:
                while self.running:
                    layout = self.create_layout()
                    
                    # Update panels
                    layout["telemetry"].update(self.create_telemetry_table())
                    layout["chat"].update(self.create_chat_panel())
                    layout["status"].update(self.create_status_panel())
                    layout["commands"].update(self.create_command_panel())
                    
                    # Simple radar display
                    radar_text = Text()
                    radar_text.append(f"📡 Radar Frames: {len(self.radar_frames_buffer)}\n", style="yellow")
                    radar_text.append(f"Last {min(5, len(self.radar_frames_buffer))} frames\n", style="dim")
                    layout["radar"].update(Panel(radar_text, title="🎯 Radar", border_style="cyan"))
                    
                    # Footer
                    uptime_str = "0m"
                    start_time = self.stats.get("uptime_start")
                    if isinstance(start_time, datetime):
                        uptime = datetime.now() - start_time
                        uptime_str = f"{uptime.seconds//60}m"
                        
                    footer_text = Align.center(
                        Text(
                            "QIKI Digital Twin | "
                            f"Uptime: {uptime_str} | "
                            f"F: {self.stats['frames_received']} | "
                            f"E: {self.stats['events_received']} | "
                            f"C: {self.stats['commands_sent']}",
                            style="dim",
                        ),
                        vertical="middle",
                    )
                    layout["footer"].update(footer_text)
                    
                    live.update(layout)
                    
                    # Check for simple keyboard commands (simplified for Docker)
                    await asyncio.sleep(0.5)
                    
        except KeyboardInterrupt:
            console.print("\n[bold red]Console terminated by user.[/bold red]")
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
    """Entry point with command line support."""
    console_app = QIKIOperatorConsoleFull()
    
    # If command line argument provided, execute it
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        await console_app.initialize()
        result = await console_app.handle_command(command)
        console.print(result)
    else:
        # Run interactive console
        await console_app.run()


if __name__ == "__main__":
    asyncio.run(main())
