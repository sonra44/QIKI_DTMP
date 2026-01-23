"""
Tests for MetricsClient functionality.
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.metrics_client import MetricsClient, MetricPoint, MetricSeries


class TestMetricPoint:
    """Test MetricPoint dataclass."""
    
    def test_metric_point_creation(self):
        """Test creating a metric point."""
        now = datetime.now()
        point = MetricPoint(timestamp=now, value=42.5)
        
        assert point.timestamp == now
        assert point.value == 42.5
        assert point.labels is None
    
    def test_metric_point_with_labels(self):
        """Test creating metric point with labels."""
        now = datetime.now()
        labels = {"service": "test", "env": "dev"}
        point = MetricPoint(timestamp=now, value=100.0, labels=labels)
        
        assert point.labels == labels


class TestMetricSeries:
    """Test MetricSeries dataclass."""
    
    def test_metric_series_creation(self):
        """Test creating a metric series."""
        from collections import deque
        
        points = deque([MetricPoint(datetime.now(), 1.0)], maxlen=100)
        series = MetricSeries(
            name="test.metric", 
            points=points,
            unit="ms",
            description="Test metric"
        )
        
        assert series.name == "test.metric"
        assert series.unit == "ms"
        assert series.description == "Test metric"
        assert len(series.points) == 1
    
    def test_metric_series_post_init(self):
        """Test metric series post init conversion to deque."""
        # Test with list instead of deque
        points = [MetricPoint(datetime.now(), 1.0)]
        series = MetricSeries(name="test", points=points)
        
        # Should be converted to deque
        assert hasattr(series.points, 'maxlen')
        assert series.points.maxlen == 1000


class TestMetricsClient:
    """Test MetricsClient functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return MetricsClient(max_points=100)
    
    def test_client_initialization(self, client):
        """Test client initializes correctly."""
        assert client.max_points == 100
        assert len(client.metrics) == 0
        assert client.collection_interval == 1.0
        assert not client.running
        assert client.nats_client is None
        assert len(client.grpc_clients) == 0
    
    def test_register_nats_client(self, client):
        """Test registering NATS client."""
        mock_nats = MagicMock()
        client.register_nats_client(mock_nats)
        
        assert client.nats_client == mock_nats
    
    def test_register_grpc_client(self, client):
        """Test registering gRPC client."""
        mock_grpc = MagicMock()
        client.register_grpc_client("sim", mock_grpc)
        
        assert "sim" in client.grpc_clients
        assert client.grpc_clients["sim"] == mock_grpc
    
    def test_add_metric(self, client):
        """Test adding a metric."""
        now = datetime.now()
        client.add_metric("test.cpu", 50.0, now, "percent", "CPU usage")
        
        assert "test.cpu" in client.metrics
        series = client.metrics["test.cpu"]
        assert series.name == "test.cpu"
        assert series.unit == "percent"
        assert series.description == "CPU usage"
        assert len(series.points) == 1
        assert series.points[0].value == 50.0
        assert series.points[0].timestamp == now
    
    def test_add_metric_default_timestamp(self, client):
        """Test adding metric with default timestamp."""
        client.add_metric("test.memory", 75.5)
        
        assert "test.memory" in client.metrics
        assert len(client.metrics["test.memory"].points) == 1
        # Should use current time
        point = client.metrics["test.memory"].points[0]
        time_diff = abs((datetime.now() - point.timestamp).total_seconds())
        assert time_diff < 1  # Within 1 second
    
    def test_get_metric(self, client):
        """Test getting metric by name."""
        client.add_metric("test.disk", 80.0)
        
        series = client.get_metric("test.disk")
        assert series is not None
        assert series.name == "test.disk"
        
        # Non-existent metric
        assert client.get_metric("nonexistent") is None
    
    def test_get_all_metrics(self, client):
        """Test getting all metrics."""
        client.add_metric("metric1", 10.0)
        client.add_metric("metric2", 20.0)
        
        all_metrics = client.get_all_metrics()
        assert len(all_metrics) == 2
        assert "metric1" in all_metrics
        assert "metric2" in all_metrics
    
    def test_get_metric_names(self, client):
        """Test getting metric names."""
        client.add_metric("cpu", 50.0)
        client.add_metric("memory", 75.0)
        
        names = client.get_metric_names()
        assert len(names) == 2
        assert "cpu" in names
        assert "memory" in names
    
    def test_get_latest_values(self, client):
        """Test getting latest values."""
        client.add_metric("test1", 10.0)
        client.add_metric("test2", 20.0)
        client.add_metric("test1", 15.0)  # Update test1
        
        latest = client.get_latest_values()
        assert latest["test1"] == 15.0
        assert latest["test2"] == 20.0
    
    def test_get_metric_history(self, client):
        """Test getting metric history."""
        now = datetime.now()
        
        # Add several points
        for i in range(5):
            timestamp = now + timedelta(seconds=i)
            client.add_metric("test.history", float(i), timestamp)
        
        # Get all history
        history = client.get_metric_history("test.history")
        assert len(history) == 5
        assert [p.value for p in history] == [0.0, 1.0, 2.0, 3.0, 4.0]
        
        # Get history for last 2 seconds
        duration = timedelta(seconds=2)
        recent_history = client.get_metric_history("test.history", duration)
        assert len(recent_history) <= 3  # Points within last 2 seconds
    
    def test_get_metric_summary(self, client):
        """Test getting metric summary."""
        now = datetime.now()
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        
        for i, val in enumerate(values):
            timestamp = now + timedelta(seconds=i)
            client.add_metric("test.summary", val, timestamp)
        
        summary = client.get_metric_summary("test.summary")
        
        assert summary["name"] == "test.summary"
        assert summary["count"] == 5
        assert summary["min"] == 10.0
        assert summary["max"] == 50.0
        assert summary["avg"] == 30.0
        assert summary["latest"] == 50.0
    
    def test_get_metric_summary_empty(self, client):
        """Test getting summary for non-existent metric."""
        summary = client.get_metric_summary("nonexistent")
        assert "error" in summary
    
    def test_clear_metrics(self, client):
        """Test clearing all metrics."""
        client.add_metric("test1", 10.0)
        client.add_metric("test2", 20.0)
        
        assert len(client.metrics) == 2
        
        client.clear_metrics()
        assert len(client.metrics) == 0
    
    def test_collect_system_metrics(self, client):
        """Test system metrics collection."""
        with (
            patch('clients.metrics_client.psutil.cpu_percent') as mock_cpu,
            patch('clients.metrics_client.psutil.virtual_memory') as mock_memory,
        ):
            mock_cpu.return_value = 45.5
            mock_memory.return_value = MagicMock(percent=75.2, available=1024 * 1024 * 1024)

            now = datetime.now()
            asyncio.run(client._collect_system_metrics(now))

            assert "system.cpu.usage_percent" in client.metrics
            assert "system.memory.usage_percent" in client.metrics
            assert "system.memory.available_mb" in client.metrics

            cpu_series = client.metrics["system.cpu.usage_percent"]
            assert cpu_series.points[-1].value == 45.5
            assert cpu_series.unit == "%"

            memory_series = client.metrics["system.memory.usage_percent"]
            assert memory_series.points[-1].value == 75.2

    def test_collect_nats_metrics_connected(self, client):
        """Test NATS metrics collection when connected."""
        mock_nats = MagicMock()
        mock_nats.is_connected = True
        mock_nats.messages_received = 100
        mock_nats.messages_processed = 95

        client.register_nats_client(mock_nats)

        now = datetime.now()
        asyncio.run(client._collect_nats_metrics(now))

        assert "nats.connection.status" in client.metrics
        assert client.metrics["nats.connection.status"].points[-1].value == 1.0

        assert "nats.messages.received_total" in client.metrics
        assert client.metrics["nats.messages.received_total"].points[-1].value == 100.0

    def test_collect_nats_metrics_disconnected(self, client):
        """Test NATS metrics collection when disconnected."""
        mock_nats = MagicMock()
        mock_nats.is_connected = False

        client.register_nats_client(mock_nats)

        now = datetime.now()
        asyncio.run(client._collect_nats_metrics(now))

        assert "nats.connection.status" in client.metrics
        assert client.metrics["nats.connection.status"].points[-1].value == 0.0

    def test_collect_grpc_metrics(self, client):
        """Test gRPC metrics collection."""
        mock_grpc = AsyncMock()
        mock_grpc.connected = True
        mock_grpc.health_check = AsyncMock()

        client.register_grpc_client("test", mock_grpc)

        now = datetime.now()
        asyncio.run(client._collect_grpc_metrics("test", mock_grpc, now))

        assert "grpc.test.connection.status" in client.metrics
        assert client.metrics["grpc.test.connection.status"].points[-1].value == 1.0

        mock_grpc.health_check.assert_called_once()

    def test_collect_app_metrics(self, client):
        """Test application metrics collection."""
        client.start_time = time.time() - 10
        client.last_collection = time.time() - 1

        now = datetime.now()
        asyncio.run(client._collect_app_metrics(now))

        assert "app.uptime_seconds" in client.metrics
        uptime = client.metrics["app.uptime_seconds"].points[-1].value
        assert 9 <= uptime <= 11

        assert "app.metrics.collection_interval_seconds" in client.metrics
        interval = client.metrics["app.metrics.collection_interval_seconds"].points[-1].value
        assert 0.5 <= interval <= 2

    def test_start_stop_collection(self, client):
        """Test starting and stopping metrics collection."""
        async def run() -> None:
            assert not client.running
            assert client.collection_task is None

            await client.start_collection()
            assert client.running
            assert client.collection_task is not None

            await asyncio.sleep(0.1)

            await client.stop_collection()
            assert not client.running

        asyncio.run(run())
    
    def test_export_json(self, client):
        """Test JSON export."""
        client.add_metric("test.export", 42.0, unit="units", description="Test metric")
        
        json_str = client.export_metrics("json")
        
        assert "test.export" in json_str
        assert "42.0" in json_str
        assert "units" in json_str
        assert "Test metric" in json_str
    
    def test_export_prometheus(self, client):
        """Test Prometheus export."""
        client.add_metric("test_prometheus", 123.45)
        
        prom_str = client.export_metrics("prometheus")
        
        assert "test_prometheus 123.45" in prom_str
        assert "Generated by QIKI" in prom_str
    
    def test_export_invalid_format(self, client):
        """Test export with invalid format."""
        with pytest.raises(ValueError):
            client.export_metrics("invalid_format")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
