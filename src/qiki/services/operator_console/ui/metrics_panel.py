"""
MetricsPanel Widget for QIKI Operator Console.
Displays system metrics with charts and real-time updates.
"""

from datetime import datetime
from typing import Dict, List, Optional
from textual.widgets import Static, Label
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from rich.console import RenderableType
from rich.table import Table
from rich.panel import Panel


class SimpleChart:
    """Simple ASCII chart for metrics visualization."""
    
    def __init__(self, width: int = 40, height: int = 8):
        self.width = width
        self.height = height
    
    def create_sparkline(self, values: List[float], title: str = "") -> str:
        """Create a simple sparkline chart."""
        if not values:
            return f"{title}: No data"
        
        if len(values) == 1:
            return f"{title}: {values[0]:.2f}"
        
        # Normalize values
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            # All values are the same
            normalized = [0.5] * len(values)
        else:
            normalized = [(v - min_val) / (max_val - min_val) for v in values]
        
        # Create sparkline
        spark_chars = "▁▂▃▄▅▆▇█"
        sparkline = ""
        
        for val in normalized[-self.width:]:  # Take last width points
            char_index = int(val * (len(spark_chars) - 1))
            sparkline += spark_chars[char_index]
        
        # Add title and latest value
        latest = values[-1] if values else 0
        return f"{title}: {sparkline} ({latest:.2f})"
    
    def create_bar_chart(self, values: List[float], labels: List[str] = None, title: str = "") -> str:
        """Create a simple horizontal bar chart."""
        if not values:
            return f"{title}: No data"
        
        lines = []
        if title:
            lines.append(title)
            lines.append("─" * len(title))
        
        max_val = max(values) if values else 1
        
        for i, val in enumerate(values):
            label = labels[i] if labels and i < len(labels) else f"Item {i+1}"
            bar_length = int((val / max_val) * 20) if max_val > 0 else 0
            bar = "█" * bar_length + "░" * (20 - bar_length)
            lines.append(f"{label:<12} │{bar}│ {val:.1f}")
        
        return "\n".join(lines)


class MetricCard(Static):
    """Card widget for displaying a single metric."""
    
    metric_name = reactive("")
    metric_value = reactive(0.0)
    metric_unit = reactive("")
    metric_status = reactive("normal")  # normal, warning, critical
    
    def __init__(self, name: str, unit: str = "", **kwargs):
        super().__init__(**kwargs)
        self.metric_name = name
        self.metric_unit = unit
        self.history: List[float] = []
        self.chart = SimpleChart(width=30)
    
    def update_value(self, value: float, status: str = "normal"):
        """Update metric value and status."""
        self.metric_value = value
        self.metric_status = status
        self.history.append(value)
        
        # Keep only last 100 points
        if len(self.history) > 100:
            self.history = self.history[-100:]
        
        self.refresh()
    
    def render(self) -> RenderableType:
        """Render metric card."""
        # Choose color based on status
        border_style = {
            "normal": "green",
            "warning": "yellow", 
            "critical": "red"
        }.get(self.metric_status, "white")
        
        # Create content
        content = []
        
        # Current value
        value_text = f"{self.metric_value:.2f}"
        if self.metric_unit:
            value_text += f" {self.metric_unit}"
        
        content.append(f"Current: [bold]{value_text}[/bold]")
        
        # Statistics if we have history
        if len(self.history) > 1:
            min_val = min(self.history)
            max_val = max(self.history)
            avg_val = sum(self.history) / len(self.history)
            
            content.append("")
            content.append(f"Min: {min_val:.2f}")
            content.append(f"Max: {max_val:.2f}")
            content.append(f"Avg: {avg_val:.2f}")
            content.append("")
            
            # Sparkline
            sparkline = self.chart.create_sparkline(self.history)
            content.append(sparkline)
        
        panel_content = "\n".join(content)
        
        return Panel(
            panel_content,
            title=f"📊 {self.metric_name}",
            border_style=border_style,
            height=10
        )


class SystemOverviewCard(Static):
    """Card showing system overview with multiple metrics."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics = {}
        self.chart = SimpleChart()
    
    def update_metrics(self, metrics_data: Dict[str, float]):
        """Update all metrics data."""
        self.metrics = metrics_data
        self.refresh()
    
    def render(self) -> RenderableType:
        """Render system overview."""
        if not self.metrics:
            return Panel(
                "No system metrics available",
                title="🖥️ System Overview",
                border_style="dim"
            )
        
        # Create table
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Metric", width=20)
        table.add_column("Value", width=15)
        table.add_column("Status", width=10)
        
        # System metrics
        cpu = self.metrics.get("system.cpu.usage_percent", 0)
        memory = self.metrics.get("system.memory.usage_percent", 0)
        uptime = self.metrics.get("app.uptime_seconds", 0)
        
        # Add rows with status colors
        cpu_status = "🟢 Good" if cpu < 70 else "🟡 High" if cpu < 90 else "🔴 Critical"
        memory_status = "🟢 Good" if memory < 80 else "🟡 High" if memory < 95 else "🔴 Critical"
        
        table.add_row("CPU Usage", f"{cpu:.1f}%", cpu_status)
        table.add_row("Memory Usage", f"{memory:.1f}%", memory_status)
        table.add_row("Uptime", f"{uptime/3600:.1f}h", "🟢 Running")
        
        # Connection status
        nats_status = self.metrics.get("nats.connection.status", 0)
        grpc_sim_status = self.metrics.get("grpc.sim.connection.status", 0)
        grpc_agent_status = self.metrics.get("grpc.agent.connection.status", 0)
        
        table.add_row("", "", "")  # Separator
        table.add_row("NATS", "Connected" if nats_status else "Disconnected", 
                     "🟢 OK" if nats_status else "🔴 Down")
        table.add_row("Q-Sim gRPC", "Connected" if grpc_sim_status else "Disconnected",
                     "🟢 OK" if grpc_sim_status else "🔴 Down")
        table.add_row("Q-Agent gRPC", "Connected" if grpc_agent_status else "Disconnected",
                     "🟢 OK" if grpc_agent_status else "🔴 Down")
        
        return Panel(
            table,
            title="🖥️ System Overview",
            border_style="bright_blue"
        )


class MetricsPanel(ScrollableContainer):
    """Main metrics panel with multiple metric cards."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics_client = None
        self.metric_cards: Dict[str, MetricCard] = {}
        self.system_overview: Optional[SystemOverviewCard] = None
        self.update_interval = 2.0  # seconds
        self.update_timer = None
    
    def set_metrics_client(self, client):
        """Set the metrics client for data collection."""
        self.metrics_client = client
    
    def compose(self):
        """Compose the metrics panel layout."""
        yield Label("📈 System Metrics", classes="panel-title")
        
        # System overview card
        self.system_overview = SystemOverviewCard(id="system-overview")
        yield self.system_overview
        
        # Individual metric cards in a grid layout
        with Horizontal():
            # CPU and Memory cards
            with Vertical():
                self.metric_cards["cpu"] = MetricCard("CPU Usage", "%", id="cpu-card")
                yield self.metric_cards["cpu"]
                
                self.metric_cards["memory"] = MetricCard("Memory Usage", "%", id="memory-card") 
                yield self.metric_cards["memory"]
        
        with Horizontal():
            # Connection metrics
            with Vertical():
                self.metric_cards["nats"] = MetricCard("NATS Status", "", id="nats-card")
                yield self.metric_cards["nats"]
                
                self.metric_cards["grpc_latency"] = MetricCard("gRPC Latency", "ms", id="grpc-card")
                yield self.metric_cards["grpc_latency"]
    
    async def on_mount(self):
        """Start periodic updates when mounted."""
        if self.metrics_client:
            self.update_timer = self.set_interval(self.update_interval, self.update_metrics)
    
    async def update_metrics(self):
        """Update all metrics from the client."""
        if not self.metrics_client:
            return
        
        try:
            # Get latest metrics
            latest = self.metrics_client.get_latest_values()
            
            if not latest:
                return
            
            # Update system overview
            if self.system_overview:
                self.system_overview.update_metrics(latest)
            
            # Update individual cards
            if "system.cpu.usage_percent" in latest:
                cpu_value = latest["system.cpu.usage_percent"]
                status = "critical" if cpu_value > 90 else "warning" if cpu_value > 70 else "normal"
                self.metric_cards["cpu"].update_value(cpu_value, status)
            
            if "system.memory.usage_percent" in latest:
                memory_value = latest["system.memory.usage_percent"]
                status = "critical" if memory_value > 95 else "warning" if memory_value > 80 else "normal"
                self.metric_cards["memory"].update_value(memory_value, status)
            
            if "nats.connection.status" in latest:
                nats_value = latest["nats.connection.status"]
                status = "normal" if nats_value > 0 else "critical"
                self.metric_cards["nats"].update_value(nats_value, status)
            
            # gRPC latency (average of available latencies)
            grpc_latencies = [v for k, v in latest.items() 
                            if "grpc." in k and "latency_ms" in k and v > 0]
            if grpc_latencies:
                avg_latency = sum(grpc_latencies) / len(grpc_latencies)
                status = "critical" if avg_latency > 1000 else "warning" if avg_latency > 500 else "normal"
                self.metric_cards["grpc_latency"].update_value(avg_latency, status)
        
        except Exception:
            # Log error but don't break the UI
            pass
    
    def get_metrics_summary(self) -> Dict[str, any]:
        """Get summary of current metrics."""
        if not self.metrics_client:
            return {"error": "No metrics client"}
        
        latest = self.metrics_client.get_latest_values()
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "metrics_count": len(latest),
            "system": {},
            "connections": {},
            "application": {}
        }
        
        # System metrics
        for key in ["system.cpu.usage_percent", "system.memory.usage_percent", "system.disk.usage_percent"]:
            if key in latest:
                summary["system"][key.replace("system.", "")] = latest[key]
        
        # Connection metrics
        for key in ["nats.connection.status", "grpc.sim.connection.status", "grpc.agent.connection.status"]:
            if key in latest:
                summary["connections"][key.replace(".connection.status", "")] = latest[key]
        
        # Application metrics
        for key in ["app.uptime_seconds", "app.metrics.tracked_count"]:
            if key in latest:
                summary["application"][key.replace("app.", "")] = latest[key]
        
        return summary
    
    def export_current_metrics(self, format: str = "json") -> str:
        """Export current metrics in specified format."""
        if not self.metrics_client:
            return '{"error": "No metrics client available"}'
        
        return self.metrics_client.export_metrics(format)


# Example usage
if __name__ == "__main__":
    from textual.app import App
    
    class MetricsTestApp(App):
        def compose(self):
            yield MetricsPanel()
    
    app = MetricsTestApp()
    app.run()