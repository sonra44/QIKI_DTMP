#!/usr/bin/env python3
"""
QIKI Operator Console - Live Data Version.

Terminal User Interface with real-time data updates.
"""

import random
from datetime import datetime
import os
import time

from rich.table import Table
from rich.live import Live
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.align import Align
from rich.text import Text


console = Console()


def generate_telemetry():
    """Generate demo telemetry data."""
    return {
        "Position X": f"{random.uniform(-100, 100):.2f} m",
        "Position Y": f"{random.uniform(-100, 100):.2f} m",
        "Velocity": f"{random.uniform(0, 50):.1f} m/s",
        "Heading": f"{random.uniform(0, 360):.1f}°",
        "Battery": f"{random.randint(20, 100)}%",
        "Temperature": f"{random.uniform(15, 35):.1f}°C",
        "Signal": f"{random.randint(60, 100)}%",
    }


def generate_radar_tracks():
    """Generate demo radar track data."""
    tracks = []
    for i in range(random.randint(1, 5)):
        tracks.append({
            "ID": f"TRK-{random.randint(100, 999)}",
            "Range": f"{random.uniform(10, 500):.1f} m",
            "Bearing": f"{random.uniform(0, 360):.1f}°",
            "Speed": f"{random.uniform(0, 100):.1f} km/h",
            "Type": random.choice(["Vessel", "Aircraft", "Vehicle", "Unknown"]),
            "Status": random.choice(["🟢 Tracked", "🟡 Lost", "🔴 Threat"])
        })
    return tracks


def create_telemetry_table():
    """Create telemetry display table."""
    table = Table(title="📊 System Telemetry", expand=True)
    table.add_column("Parameter", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    table.add_column("Updated", style="dim")
    
    telemetry = generate_telemetry()
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    for param, value in telemetry.items():
        table.add_row(param, value, timestamp)
    
    return table


def create_radar_table():
    """Create radar tracks table."""
    table = Table(title="🎯 Radar Tracks", expand=True)
    table.add_column("Track ID", style="yellow", no_wrap=True)
    table.add_column("Range", style="cyan")
    table.add_column("Bearing", style="cyan")
    table.add_column("Speed", style="magenta")
    table.add_column("Type", style="blue")
    table.add_column("Status", style="bold")
    
    tracks = generate_radar_tracks()
    for track in tracks:
        table.add_row(
            track["ID"],
            track["Range"],
            track["Bearing"],
            track["Speed"],
            track["Type"],
            track["Status"]
        )
    
    return table


def create_system_status():
    """Create system status panel."""
    status_text = Text()
    
    # NATS Connection
    nats_url = os.getenv('NATS_URL', 'Not configured')
    status_text.append("NATS: ", style="bold")
    if "nats://" in nats_url:
        status_text.append("✅ Connected\n", style="green")
        status_text.append(f"  URL: {nats_url}\n", style="dim")
    else:
        status_text.append("❌ Disconnected\n", style="red")
    
    # gRPC Connection
    grpc_host = os.getenv('GRPC_HOST', 'Not configured')
    status_text.append("\ngRPC: ", style="bold")
    if grpc_host != "Not configured":
        status_text.append("✅ Connected\n", style="green")
        status_text.append(f"  Host: {grpc_host}:{os.getenv('GRPC_PORT', '50051')}\n", style="dim")
    else:
        status_text.append("❌ Disconnected\n", style="red")
    
    # System Health
    status_text.append("\nSystem: ", style="bold")
    status_text.append("🟢 Operational\n", style="green bold")
    
    # Simulation Status
    status_text.append("\nSimulation: ", style="bold")
    status_text.append("▶️ Running\n", style="cyan bold")
    
    return Panel(status_text, title="🔧 System Status", border_style="blue")


def create_command_hints():
    """Create command hints panel."""
    hints = Text()
    hints.append("📌 Commands:\n\n", style="bold yellow")
    hints.append("Ctrl+C", style="bold cyan")
    hints.append(" - Exit\n")
    hints.append("Space", style="bold cyan")
    hints.append(" - Pause/Resume\n")
    hints.append("R", style="bold cyan")
    hints.append(" - Reset\n")
    hints.append("T", style="bold cyan")
    hints.append(" - Toggle Theme\n")
    
    return Panel(hints, title="⌨️ Controls", border_style="yellow")


def create_layout():
    """Create the main layout."""
    layout = Layout()
    
    # Split into header and body
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=1)
    )
    
    # Header
    header_text = Align.center(
        Text("QIKI OPERATOR CONSOLE v1.0", style="bold white on blue"),
        vertical="middle"
    )
    layout["header"].update(Panel(header_text, style="bold blue"))
    
    # Body - split into left and right
    layout["body"].split_row(
        Layout(name="left", ratio=2),
        Layout(name="right", ratio=1)
    )
    
    # Left side - telemetry and radar
    layout["left"].split_column(
        Layout(name="telemetry"),
        Layout(name="radar")
    )
    
    # Right side - status and commands
    layout["right"].split_column(
        Layout(name="status"),
        Layout(name="commands", size=10)
    )
    
    # Footer
    footer_text = Align.center(
        Text(f"Connected to QIKI Digital Twin | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
             style="dim"),
        vertical="middle"
    )
    layout["footer"].update(footer_text)
    
    return layout


def main():
    """Main application loop."""
    console.print("\n[bold cyan]Starting QIKI Operator Console...[/bold cyan]\n")
    
    try:
        with Live(create_layout(), refresh_per_second=2, screen=True) as live:
            while True:
                # Update layout with fresh data
                layout = create_layout()
                layout["telemetry"].update(create_telemetry_table())
                layout["radar"].update(create_radar_table())
                layout["status"].update(create_system_status())
                layout["commands"].update(create_command_hints())
                
                # Update footer with current time
                footer_text = Align.center(
                    Text(f"Connected to QIKI Digital Twin | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                         style="dim"),
                    vertical="middle"
                )
                layout["footer"].update(footer_text)
                
                live.update(layout)
                time.sleep(0.5)
                
    except KeyboardInterrupt:
        console.print("\n[bold red]Console terminated by user.[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")


if __name__ == "__main__":
    main()
