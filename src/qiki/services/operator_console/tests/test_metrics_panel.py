"""
Tests for MetricsPanel widget.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from textual.app import App, ComposeResult
from textual.widgets import Widget
from textual.screen import Screen
from widgets.metrics_panel import MetricsPanel
from clients.metrics_client import MetricsClient


class MockApp(App):
    """Mock Textual app for testing."""
    
    def __init__(self):
        super().__init__()
        self.metrics_client = MetricsClient(max_points=100)
    
    def compose(self) -> ComposeResult:
        yield MetricsPanel()


@pytest.fixture
def metrics_client():
    """Create test metrics client."""
    client = MetricsClient(max_points=100)
    
    # Add some test metrics
    now = datetime.now()
    for i in range(10):
        timestamp = now + timedelta(seconds=i)
        client.add_metric("cpu.usage", float(50 + i), timestamp, "%", "CPU Usage")
        client.add_metric("memory.usage", float(75 - i), timestamp, "%", "Memory Usage")
        client.add_metric("disk.usage", float(80), timestamp, "%", "Disk Usage")
    
    return client


@pytest.fixture
def panel():
    """Create test panel."""
    return MetricsPanel()


class TestMetricsPanel:
    """Test MetricsPanel functionality."""
    
    def test_panel_initialization(self, panel):
        """Test panel initializes correctly."""
        assert panel.id == "metrics_panel"
        assert panel.title == "System Metrics"
        assert panel.can_focus is True
        assert not panel.auto_refresh
        assert panel.refresh_interval == 2.0
    
    def test_panel_with_client(self, metrics_client):
        """Test panel with metrics client."""
        panel = MetricsPanel(metrics_client=metrics_client)
        assert panel.metrics_client is metrics_client
    
    def test_format_value_basic(self, panel):
        """Test basic value formatting."""
        assert panel._format_value(50.123, None) == "50.12"
        assert panel._format_value(0.123, None) == "0.12"
        assert panel._format_value(1000.0, None) == "1000.00"
    
    def test_format_value_with_unit(self, panel):
        """Test value formatting with units."""
        assert panel._format_value(50.5, "%") == "50.50%"
        assert panel._format_value(1024.0, "MB") == "1024.00 MB"
        assert panel._format_value(0.001, "ms") == "0.00ms"
    
    def test_format_bytes(self, panel):
        """Test byte formatting."""
        assert panel._format_bytes(1024) == "1.00 KB"
        assert panel._format_bytes(1024 * 1024) == "1.00 MB"
        assert panel._format_bytes(1024 * 1024 * 1024) == "1.00 GB"
        assert panel._format_bytes(1024 * 1024 * 1024 * 1024) == "1.00 TB"
        assert panel._format_bytes(512) == "512.00 B"
    
    def test_create_bar_chart_empty(self, panel):
        """Test creating bar chart with empty data."""
        result = panel._create_bar_chart([], 10)
        assert result == "No data"
    
    def test_create_bar_chart_basic(self, panel):
        """Test creating basic bar chart."""
        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = panel._create_bar_chart(data, 20)
        
        # Should contain bar characters and show progression
        assert "▓" in result or "▒" in result or "░" in result
        assert len(result) <= 20 * 5  # Width * height estimation
    
    def test_create_bar_chart_single_value(self, panel):
        """Test bar chart with single value."""
        result = panel._create_bar_chart([100.0], 10)
        assert len(result) > 0
        assert "100%" in result or "▓" in result
    
    def test_create_line_graph_empty(self, panel):
        """Test creating line graph with empty data."""
        result = panel._create_line_graph([], 10)
        assert result == "No data"
    
    def test_create_line_graph_basic(self, panel):
        """Test creating basic line graph."""
        data = [1.0, 2.0, 3.0, 2.0, 1.0]
        result = panel._create_line_graph(data, 20)
        
        # Should contain graph characters
        assert any(char in result for char in ["*", "-", "|", "+"])
        assert len(result) > 0
    
    def test_create_summary_table_empty(self, panel):
        """Test creating summary table with no metrics."""
        result = panel._create_summary_table({})
        assert "No metrics available" in result
    
    def test_create_summary_table_with_data(self, panel, metrics_client):
        """Test creating summary table with metrics."""
        panel.metrics_client = metrics_client
        
        # Get some metrics summaries
        summaries = {}
        for name in metrics_client.get_metric_names():
            summaries[name] = metrics_client.get_metric_summary(name)
        
        result = panel._create_summary_table(summaries)
        
        # Should contain metric names and values
        assert "cpu.usage" in result
        assert "memory.usage" in result 
        assert "disk.usage" in result
        assert "%" in result  # Unit symbols
    
    def test_create_recent_metrics_empty(self, panel):
        """Test creating recent metrics with no data."""
        result = panel._create_recent_metrics([])
        assert "No recent metrics" in result
    
    def test_create_recent_metrics_with_data(self, panel, metrics_client):
        """Test creating recent metrics display."""
        panel.metrics_client = metrics_client
        
        # Get latest values
        latest = metrics_client.get_latest_values()
        recent = []
        for name, value in latest.items():
            metric = metrics_client.get_metric(name)
            recent.append({
                'name': name,
                'value': value,
                'unit': metric.unit,
                'timestamp': metric.points[-1].timestamp
            })
        
        result = panel._create_recent_metrics(recent)
        
        assert "cpu.usage" in result
        assert "memory.usage" in result
        assert len(result) > 0
    
    @patch('widgets.metrics_panel.MetricsPanel._create_summary_table')
    @patch('widgets.metrics_panel.MetricsPanel._create_recent_metrics')
    def test_get_content_no_client(self, mock_recent, mock_summary, panel):
        """Test getting content without metrics client."""
        mock_summary.return_value = "No client"
        mock_recent.return_value = "No client"
        
        content = panel._get_content()
        
        assert "Metrics Collection: Disabled" in content
        mock_summary.assert_called_once_with({})
        mock_recent.assert_called_once_with([])
    
    def test_get_content_with_client(self, panel, metrics_client):
        """Test getting content with metrics client."""
        panel.metrics_client = metrics_client
        
        content = panel._get_content()
        
        assert "Metrics Collection: Active" in content
        assert "cpu.usage" in content
        assert "memory.usage" in content
    
    def test_get_content_view_modes(self, panel, metrics_client):
        """Test different view modes."""
        panel.metrics_client = metrics_client
        
        # Test summary view (default)
        panel.view_mode = "summary"
        content = panel._get_content()
        assert "Summary" in content
        
        # Test graphs view
        panel.view_mode = "graphs" 
        content = panel._get_content()
        assert "CPU Usage" in content
        
        # Test raw view
        panel.view_mode = "raw"
        content = panel._get_content()
        assert "Recent Values" in content
    
    def test_toggle_refresh(self, panel):
        """Test toggling auto refresh."""
        # Initially disabled
        assert not panel.auto_refresh
        
        panel._toggle_refresh()
        assert panel.auto_refresh
        
        panel._toggle_refresh()
        assert not panel.auto_refresh
    
    def test_cycle_view_mode(self, panel):
        """Test cycling through view modes."""
        assert panel.view_mode == "summary"
        
        panel._cycle_view_mode()
        assert panel.view_mode == "graphs"
        
        panel._cycle_view_mode()
        assert panel.view_mode == "raw"
        
        panel._cycle_view_mode()
        assert panel.view_mode == "summary"  # Back to start
    
    def test_export_metrics_no_client(self, panel):
        """Test exporting metrics without client."""
        result = panel._export_metrics("json")
        assert result == "No metrics client available"
    
    def test_export_metrics_with_client(self, panel, metrics_client):
        """Test exporting metrics with client."""
        panel.metrics_client = metrics_client
        
        # Test JSON export
        result = panel._export_metrics("json")
        assert "cpu.usage" in result
        assert "{" in result  # JSON format
        
        # Test Prometheus export
        result = panel._export_metrics("prometheus")
        assert "cpu_usage" in result or "cpu.usage" in result
    
    @pytest.mark.asyncio
    async def test_refresh_task(self, panel, metrics_client):
        """Test refresh task functionality."""
        panel.metrics_client = metrics_client
        panel.auto_refresh = True
        
        # Mock the update method
        panel.update = MagicMock()
        
        # Start refresh task
        panel._start_refresh_task()
        assert panel._refresh_task is not None
        
        # Let it run briefly
        await asyncio.sleep(0.1)
        
        # Stop refresh task
        panel._stop_refresh_task()
        
        # Update should have been called
        panel.update.assert_called()
    
    def test_key_bindings(self, panel):
        """Test key binding methods exist and work."""
        # Test that key binding methods exist
        assert hasattr(panel, '_toggle_refresh')
        assert hasattr(panel, '_cycle_view_mode')
        assert hasattr(panel, '_export_metrics')
        
        # Test methods don't crash
        panel._toggle_refresh()
        panel._cycle_view_mode()
        result = panel._export_metrics("json")
        assert isinstance(result, str)


@pytest.mark.asyncio
async def test_panel_integration():
    """Integration test with mock app."""
    app = MockApp()
    
    # Add test data to metrics client
    now = datetime.now()
    app.metrics_client.add_metric("test.cpu", 45.0, now, "%", "CPU")
    app.metrics_client.add_metric("test.memory", 60.0, now, "%", "Memory")
    
    # Create panel with client
    panel = MetricsPanel(metrics_client=app.metrics_client)
    
    # Test content generation
    content = panel._get_content()
    assert "Metrics Collection: Active" in content
    assert "test.cpu" in content
    assert "test.memory" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])