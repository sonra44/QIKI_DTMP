"""
Metrics Client for QIKI Operator Console.
Collects system metrics from NATS, gRPC services, and internal sensors.
"""

import asyncio
import logging
import time
from typing import Any, Deque, Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import deque
import psutil


logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: datetime
    value: float
    labels: Optional[Dict[str, str]] = None


@dataclass  
class MetricSeries:
    """Time series of metric values."""
    name: str
    points: Deque[MetricPoint]
    unit: str = ""
    description: str = ""
    
    def __post_init__(self):
        if not hasattr(self.points, 'maxlen'):
            # Convert to deque if not already
            self.points = deque(self.points, maxlen=1000)


class MetricsClient:
    """Client for collecting and managing system metrics."""
    
    def __init__(self, max_points: int = 1000):
        """
        Initialize metrics client.
        
        Args:
            max_points: Maximum points to keep per metric series
        """
        self.max_points = max_points
        self.metrics: Dict[str, MetricSeries] = {}
        self.collection_interval = 1.0  # seconds
        self.collection_task: Optional[asyncio.Task] = None
        self.running = False
        
        # External clients for metrics collection
        self.nats_client: Optional[Any] = None
        self.grpc_clients: Dict[str, Any] = {}
        
        # Internal counters
        self.start_time = time.time()
        self.last_collection = time.time()
        
    def register_nats_client(self, nats_client: Any) -> None:
        """Register NATS client for metrics collection."""
        self.nats_client = nats_client
        
    def register_grpc_client(self, name: str, grpc_client: Any) -> None:
        """Register gRPC client for metrics collection."""
        self.grpc_clients[name] = grpc_client
    
    async def start_collection(self):
        """Start automatic metrics collection."""
        if self.running:
            return
            
        self.running = True
        self.collection_task = asyncio.create_task(self._collection_loop())
        logger.info("✅ Metrics collection started")
    
    async def stop_collection(self):
        """Stop metrics collection."""
        self.running = False
        if self.collection_task and not self.collection_task.done():
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️ Metrics collection stopped")
    
    async def _collection_loop(self):
        """Main metrics collection loop."""
        while self.running:
            try:
                await self._collect_all_metrics()
                await asyncio.sleep(self.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in metrics collection: {e}")
                await asyncio.sleep(self.collection_interval)
    
    async def _collect_all_metrics(self):
        """Collect all available metrics."""
        now = datetime.now()
        
        # System metrics
        await self._collect_system_metrics(now)
        
        # NATS metrics
        if self.nats_client:
            await self._collect_nats_metrics(now)
        
        # gRPC metrics
        for name, client in self.grpc_clients.items():
            await self._collect_grpc_metrics(name, client, now)
        
        # Application metrics
        await self._collect_app_metrics(now)
        
        self.last_collection = time.time()
    
    async def _collect_system_metrics(self, timestamp: datetime):
        """Collect system performance metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            self.add_metric("system.cpu.usage_percent", cpu_percent, timestamp, 
                          unit="%", description="CPU usage percentage")
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.add_metric("system.memory.usage_percent", memory.percent, timestamp,
                          unit="%", description="Memory usage percentage")
            self.add_metric("system.memory.available_mb", memory.available / 1024 / 1024, timestamp,
                          unit="MB", description="Available memory")
            
            # Disk usage (if available)
            try:
                disk = psutil.disk_usage('/')
                disk_percent = (disk.used / disk.total) * 100
                self.add_metric("system.disk.usage_percent", disk_percent, timestamp,
                              unit="%", description="Disk usage percentage")
            except (OSError, PermissionError):
                # Windows or permission issue
                pass
                
        except Exception as e:
            logger.error(f"❌ Error collecting system metrics: {e}")
    
    async def _collect_nats_metrics(self, timestamp: datetime) -> None:
        """Collect NATS-related metrics."""
        client = self.nats_client
        if client is None:
            return
        try:
            if getattr(client, "is_connected", False):
                # Connection status
                self.add_metric("nats.connection.status", 1.0, timestamp,
                                description="NATS connection status (1=connected, 0=disconnected)")
                
                # Message processing metrics (if available)
                if hasattr(client, 'messages_received'):
                    self.add_metric("nats.messages.received_total", 
                                  float(getattr(client, 'messages_received', 0)), 
                                  timestamp, description="Total messages received")
                
                if hasattr(client, 'messages_processed'):
                    self.add_metric("nats.messages.processed_total",
                                  float(getattr(client, 'messages_processed', 0)),
                                  timestamp, description="Total messages processed")
            else:
                self.add_metric("nats.connection.status", 0.0, timestamp,
                                description="NATS connection status")
                                
        except Exception as e:
            logger.error(f"❌ Error collecting NATS metrics: {e}")
    
    async def _collect_grpc_metrics(self, name: str, client: Any, timestamp: datetime):
        """Collect gRPC client metrics."""
        try:
            # Connection status
            connected = 1.0 if getattr(client, 'connected', False) else 0.0
            self.add_metric(f"grpc.{name}.connection.status", connected, timestamp,
                          description=f"{name} gRPC connection status")
            
            # Health check latency (if supported)
            if hasattr(client, 'health_check') and connected:
                start_time = time.time()
                try:
                    await client.health_check()
                    latency_ms = (time.time() - start_time) * 1000
                    self.add_metric(f"grpc.{name}.health_check.latency_ms", latency_ms, timestamp,
                                  unit="ms", description=f"{name} health check latency")
                except Exception:
                    # Health check failed
                    self.add_metric(f"grpc.{name}.health_check.latency_ms", -1, timestamp,
                                  unit="ms", description=f"{name} health check latency (failed)")
                                  
        except Exception as e:
            logger.error(f"❌ Error collecting {name} gRPC metrics: {e}")
    
    async def _collect_app_metrics(self, timestamp: datetime):
        """Collect application-specific metrics."""
        try:
            # Uptime
            uptime_seconds = time.time() - self.start_time
            self.add_metric("app.uptime_seconds", uptime_seconds, timestamp,
                          unit="s", description="Application uptime")
            
            # Collection frequency
            collection_interval = time.time() - self.last_collection
            self.add_metric("app.metrics.collection_interval_seconds", collection_interval, timestamp,
                          unit="s", description="Time between metric collections")
            
            # Number of tracked metrics
            metrics_count = len(self.metrics)
            self.add_metric("app.metrics.tracked_count", float(metrics_count), timestamp,
                          description="Number of tracked metrics")
            
        except Exception as e:
            logger.error(f"❌ Error collecting app metrics: {e}")
    
    def add_metric(
        self,
        name: str,
        value: float,
        timestamp: Optional[datetime] = None,
        unit: str = "",
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Add a metric data point.
        
        Args:
            name: Metric name
            value: Metric value
            timestamp: Timestamp (defaults to now)
            unit: Unit of measurement
            description: Metric description
            labels: Optional labels
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        # Create metric series if it doesn't exist
        if name not in self.metrics:
            self.metrics[name] = MetricSeries(
                name=name,
                points=deque(maxlen=self.max_points),
                unit=unit,
                description=description
            )
        
        # Add data point
        point = MetricPoint(timestamp=timestamp, value=value, labels=labels)
        self.metrics[name].points.append(point)
    
    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get metric series by name."""
        return self.metrics.get(name)
    
    def get_all_metrics(self) -> Dict[str, MetricSeries]:
        """Get all metric series."""
        return self.metrics.copy()
    
    def get_metric_names(self) -> List[str]:
        """Get list of all metric names."""
        return list(self.metrics.keys())
    
    def get_latest_values(self) -> Dict[str, float]:
        """Get latest values for all metrics."""
        latest = {}
        for name, series in self.metrics.items():
            if series.points:
                latest[name] = series.points[-1].value
        return latest
    
    def get_metric_history(self, name: str, duration: Optional[timedelta] = None) -> List[MetricPoint]:
        """
        Get metric history for specified duration.
        
        Args:
            name: Metric name
            duration: Time duration (defaults to all available)
            
        Returns:
            List of metric points
        """
        if name not in self.metrics:
            return []
        
        points = list(self.metrics[name].points)
        
        if duration is None:
            return points
        
        cutoff_time = datetime.now() - duration
        return [point for point in points if point.timestamp >= cutoff_time]
    
    def get_metric_summary(self, name: str, duration: Optional[timedelta] = None) -> Dict[str, Any]:
        """
        Get metric summary statistics.
        
        Args:
            name: Metric name
            duration: Time duration
            
        Returns:
            Dictionary with min, max, avg, count statistics
        """
        points = self.get_metric_history(name, duration)
        
        if not points:
            return {"error": "No data available"}
        
        values = [point.value for point in points]
        
        return {
            "name": name,
            "unit": self.metrics[name].unit,
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1] if values else None,
            "first_timestamp": points[0].timestamp.isoformat(),
            "latest_timestamp": points[-1].timestamp.isoformat()
        }
    
    def clear_metrics(self):
        """Clear all collected metrics."""
        self.metrics.clear()
        logger.info("📊 Metrics cleared")
    
    def export_metrics(self, format: str = "json") -> str:
        """
        Export metrics in specified format.
        
        Args:
            format: Export format ('json' or 'prometheus')
            
        Returns:
            Formatted metrics string
        """
        if format.lower() == "json":
            return self._export_json()
        elif format.lower() == "prometheus":
            return self._export_prometheus()
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_json(self) -> str:
        """Export metrics as JSON."""
        import json
        
        export_data: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {}
        }
        
        for name, series in self.metrics.items():
            points_data = []
            for point in list(series.points)[-100:]:  # Last 100 points
                points_data.append({
                    "timestamp": point.timestamp.isoformat(),
                    "value": point.value,
                    "labels": point.labels
                })
            
            export_data["metrics"][name] = {
                "unit": series.unit,
                "description": series.description,
                "points": points_data
            }
        
        return json.dumps(export_data, indent=2)
    
    def _export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        lines.append(f"# Generated by QIKI Operator Console at {datetime.now().isoformat()}")
        lines.append("")
        
        for name, series in self.metrics.items():
            if series.description:
                lines.append(f"# HELP {name} {series.description}")
            if series.unit:
                lines.append(f"# TYPE {name} gauge")
            
            # Latest value
            if series.points:
                latest = series.points[-1]
                labels_str = ""
                if latest.labels:
                    label_parts = [f'{k}="{v}"' for k, v in latest.labels.items()]
                    labels_str = "{" + ",".join(label_parts) + "}"
                
                lines.append(f"{name}{labels_str} {latest.value}")
            
            lines.append("")
        
        return "\n".join(lines)


# Example usage
async def main():
    """Example of metrics client usage."""
    client = MetricsClient()
    
    # Start collection
    await client.start_collection()
    
    # Let it collect for a few seconds
    await asyncio.sleep(5)
    
    # Get some metrics
    latest = client.get_latest_values()
    print("Latest metrics:", latest)
    
    # Get summary for CPU
    cpu_summary = client.get_metric_summary("system.cpu.usage_percent")
    print("CPU summary:", cpu_summary)
    
    # Export metrics
    json_export = client.export_metrics("json")
    print("JSON export length:", len(json_export))
    
    # Stop collection
    await client.stop_collection()


if __name__ == "__main__":
    asyncio.run(main())
