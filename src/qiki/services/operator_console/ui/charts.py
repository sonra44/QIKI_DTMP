"""
Charts and metrics visualization for Operator Console.

Provides sparklines, histograms and other visual components.
"""

from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple
from collections import deque
from datetime import datetime
import math

from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.console import Console


class Sparkline:
    """Create sparkline charts for time series data."""

    BARS = " ▁▂▃▄▅▆▇█"

    def __init__(self, data: Sequence[float], width: int = 20, height: int = 1):
        """
        Initialize sparkline.

        Args:
            data: List of values to plot
            width: Width of the chart in characters
            height: Height (not used yet, for future multi-line charts)
        """
        data_list = [float(val) for val in data]
        self.data: List[float] = data_list[-width:] if len(data_list) > width else data_list
        self.width = width
        self.height = height

    def render(self) -> str:
        """Render sparkline as string."""
        if not self.data:
            return "─" * self.width

        min_val = min(self.data)
        max_val = max(self.data)

        if max_val == min_val:
            # All values are the same
            return self.BARS[4] * len(self.data)

        # Normalize data to 0-8 range (for bar characters)
        normalized = []
        for val in self.data:
            norm = (val - min_val) / (max_val - min_val)
            bar_idx = int(norm * (len(self.BARS) - 1))
            normalized.append(self.BARS[bar_idx])

        # Pad if needed
        if len(normalized) < self.width:
            padding = " " * (self.width - len(normalized))
            normalized = list(padding) + normalized

        return "".join(normalized)

    def __str__(self) -> str:
        """String representation."""
        return self.render()


class ProgressBar:
    """Simple progress bar visualization."""

    def __init__(self, value: float, max_value: float = 100, width: int = 20, show_percentage: bool = True):
        """Initialize progress bar."""
        self.value = min(value, max_value)
        self.max_value = max_value
        self.width = width
        self.show_percentage = show_percentage

    def render(self) -> str:
        """Render progress bar."""
        if self.max_value == 0:
            percentage: float = 0.0
            filled_width = 0
        else:
            percentage = (self.value / self.max_value) * 100
            filled_width = int((self.value / self.max_value) * self.width)

        empty_width = self.width - filled_width

        bar = "█" * filled_width + "░" * empty_width

        if self.show_percentage:
            return f"[{bar}] {percentage:.1f}%"
        else:
            return f"[{bar}]"

    def __str__(self) -> str:
        """String representation."""
        return self.render()


class MetricsHistory:
    """Store and manage metrics history for visualization."""

    def __init__(self, max_points: int = 100):
        """
        Initialize metrics history.

        Args:
            max_points: Maximum number of data points to keep
        """
        self.max_points = max_points
        self.metrics: Dict[str, Deque[Dict[str, Any]]] = {}

    def add_metric(self, name: str, value: float, timestamp: Optional[datetime] = None):
        """Add a metric value."""
        if timestamp is None:
            timestamp = datetime.now()

        if name not in self.metrics:
            self.metrics[name] = deque(maxlen=self.max_points)

        self.metrics[name].append({"value": float(value), "timestamp": timestamp})

    def get_values(self, name: str, last_n: Optional[int] = None) -> List[float]:
        """Get metric values."""
        if name not in self.metrics:
            return []

        data = list(self.metrics[name])
        if last_n:
            data = data[-last_n:]

        return [d["value"] for d in data]

    def get_sparkline(self, name: str, width: int = 20) -> str:
        """Get sparkline for a metric."""
        values = self.get_values(name)
        if not values:
            return "─" * width

        sparkline = Sparkline(values, width=width)
        return sparkline.render()

    def get_average(self, name: str, last_n: Optional[int] = None) -> float:
        """Get average value of a metric."""
        values = self.get_values(name, last_n)
        if not values:
            return 0.0
        return sum(values) / len(values)

    def get_min_max(self, name: str) -> Tuple[float, float]:
        """Get min and max values."""
        values = self.get_values(name)
        if not values:
            return (0.0, 0.0)
        return (min(values), max(values))


class MetricsPanel:
    """Rich panel for displaying metrics with charts."""

    def __init__(self, history: MetricsHistory, title: str = "📈 Metrics"):
        """Initialize metrics panel."""
        self.history = history
        self.title = title

    def create_panel(self) -> Panel:
        """Create a Rich panel with metrics."""
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Metric", style="yellow", no_wrap=True)
        table.add_column("Current", style="green")
        table.add_column("Avg", style="cyan")
        table.add_column("Min/Max", style="dim")
        table.add_column("Trend (last 20)", style="white")

        for metric_name in self.history.metrics:
            values = self.history.get_values(metric_name)
            if not values:
                continue

            current = values[-1] if values else 0
            avg = self.history.get_average(metric_name)
            min_val, max_val = self.history.get_min_max(metric_name)
            sparkline = self.history.get_sparkline(metric_name, width=20)

            # Format values based on metric type
            if "battery" in metric_name.lower() or "percent" in metric_name.lower():
                current_str = f"{current:.0f}%"
                avg_str = f"{avg:.0f}%"
                minmax_str = f"{min_val:.0f}/{max_val:.0f}%"
            elif "position" in metric_name.lower() or "distance" in metric_name.lower():
                current_str = f"{current:.2f}m"
                avg_str = f"{avg:.2f}m"
                minmax_str = f"{min_val:.1f}/{max_val:.1f}m"
            elif "velocity" in metric_name.lower() or "speed" in metric_name.lower():
                current_str = f"{current:.1f}m/s"
                avg_str = f"{avg:.1f}m/s"
                minmax_str = f"{min_val:.1f}/{max_val:.1f}"
            else:
                current_str = f"{current:.2f}"
                avg_str = f"{avg:.2f}"
                minmax_str = f"{min_val:.1f}/{max_val:.1f}"

            table.add_row(metric_name, current_str, avg_str, minmax_str, sparkline)

        return Panel(table, title=self.title, border_style="blue")


class RadarVisualization:
    """ASCII visualization of radar detections."""

    def __init__(self, width: int = 40, height: int = 20):
        """Initialize radar visualization."""
        self.width = width
        self.height = height
        self.center_x = width // 2
        self.center_y = height // 2

    def plot_detection(self, grid: List[List[str]], range_m: float, bearing_deg: float, max_range: float = 500.0):
        """Plot a single detection on the grid."""
        # Convert polar to cartesian
        bearing_rad = math.radians(bearing_deg)
        normalized_range = min(range_m / max_range, 1.0)

        x = int(self.center_x + normalized_range * self.center_x * math.sin(bearing_rad))
        y = int(self.center_y - normalized_range * self.center_y * math.cos(bearing_rad))

        if 0 <= x < self.width and 0 <= y < self.height:
            grid[y][x] = "●"

    def render(self, detections: List[dict], *, max_range_m: float = 500.0) -> str:
        """
        Render radar display with detections.

        Args:
            detections: List of detection dicts with 'range' and 'bearing' keys
        """
        # Create empty grid
        grid = [[" " for _ in range(self.width)] for _ in range(self.height)]

        # Draw radar circles
        for radius in [0.25, 0.5, 0.75, 1.0]:
            self.draw_circle(grid, radius)

        # Draw center
        grid[self.center_y][self.center_x] = "+"

        # Plot detections
        for det in detections:
            if "range" in det and "bearing" in det:
                self.plot_detection(grid, det["range"], det["bearing"], max_range=max_range_m)

        # Convert grid to string
        lines = []
        for row in grid:
            lines.append("".join(row))

        return "\n".join(lines)

    def draw_circle(self, grid: List[List[str]], radius_ratio: float) -> None:
        """Draw a circle on the grid."""
        steps = 36  # Number of points to draw
        for i in range(steps):
            angle = 2 * math.pi * i / steps
            x = int(self.center_x + radius_ratio * self.center_x * math.sin(angle))
            y = int(self.center_y + radius_ratio * self.center_y * math.cos(angle))

            if 0 <= x < self.width and 0 <= y < self.height and grid[y][x] == " ":
                grid[y][x] = "·"


class PpiScopeRenderer:
    """Minimal radar PPI renderer used by ORION (optional; no hard deps)."""

    def __init__(self, *, width: int, height: int, max_range_m: float) -> None:
        self._viz = RadarVisualization(width=width, height=height)
        self._max_range_m = float(max_range_m)

    def render_tracks(self, tracks: List[dict[str, Any]]) -> str:
        detections: List[dict] = []
        for t in tracks:
            if not isinstance(t, dict):
                continue
            r = t.get("range_m")
            b = t.get("bearing_deg")
            if not isinstance(r, (int, float, str)) or not isinstance(b, (int, float, str)):
                continue
            try:
                r_f = float(r)
                b_f = float(b)
            except Exception:
                continue
            detections.append({"range": r_f, "bearing": b_f})
        return self._viz.render(detections, max_range_m=self._max_range_m)


class BatteryIndicator:
    """Battery level indicator with color coding."""

    @staticmethod
    def render(level: float, width: int = 10) -> Text:
        """Render battery indicator."""
        if level > 75:
            color = "green"
            icon = "🔋"
        elif level > 50:
            color = "yellow"
            icon = "🔋"
        elif level > 25:
            color = "orange"
            icon = "🪫"
        else:
            color = "red"
            icon = "🪫"

        bar = ProgressBar(level, 100, width, show_percentage=False)

        text = Text()
        text.append(f"{icon} ", style=color)
        text.append(bar.render(), style=color)
        text.append(f" {level:.0f}%", style=f"bold {color}")

        return text


class SignalStrength:
    """Signal strength indicator."""

    @staticmethod
    def render(strength: float) -> str:
        """Render signal strength bars."""
        if strength > 80:
            return "📶 ▁▃▅▇█"
        elif strength > 60:
            return "📶 ▁▃▅▇░"
        elif strength > 40:
            return "📶 ▁▃▅░░"
        elif strength > 20:
            return "📶 ▁▃░░░"
        else:
            return "📵 ▁░░░░"


# Example usage
if __name__ == "__main__":
    # Test sparkline
    data = [10, 15, 20, 18, 25, 30, 28, 35, 32, 40]
    spark = Sparkline(data)
    print(f"Sparkline: {spark}")

    # Test progress bar
    progress = ProgressBar(75, 100)
    print(f"Progress: {progress}")

    # Test metrics history
    history = MetricsHistory()
    for i in range(20):
        history.add_metric("velocity", 20 + i * 0.5)
        history.add_metric("battery", 100 - i * 2)

    print(f"Velocity trend: {history.get_sparkline('velocity')}")
    print(f"Battery trend: {history.get_sparkline('battery')}")

    # Test battery indicator
    battery = BatteryIndicator.render(45)
    console = Console()
    console.print(battery)

    # Test signal strength
    signal = SignalStrength.render(75)
    print(f"Signal: {signal}")
