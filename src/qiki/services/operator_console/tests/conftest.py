"""
Shared pytest fixtures and configuration for QIKI Operator Console tests.
"""

import pytest
import asyncio
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

# Import components for fixtures
from qiki.services.operator_console.clients.metrics_client import MetricsClient
from qiki.services.operator_console.clients.grpc_client import QSimGrpcClient, QAgentGrpcClient
from qiki.services.operator_console.core.i18n import I18n


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_metrics_client():
    """Create a mock metrics client with sample data."""
    client = MetricsClient(max_points=100)

    # Add sample metrics
    now = datetime.now()
    for i in range(10):
        timestamp = now + timedelta(seconds=i)
        client.add_metric("cpu.usage", float(50 + i % 20), timestamp, "%", "CPU Usage")
        client.add_metric("memory.usage", float(60 + i % 30), timestamp, "%", "Memory Usage")
        client.add_metric("disk.usage", float(70 + i % 10), timestamp, "%", "Disk Usage")
        client.add_metric("network.rx", float(100 + i * 10), timestamp, "KB/s", "Network RX")
        client.add_metric("network.tx", float(80 + i * 8), timestamp, "KB/s", "Network TX")

    return client


@pytest.fixture
def mock_simulation_client():
    """Create a mock simulation gRPC client."""
    client = QSimGrpcClient("localhost", 50051)
    client.connected = True

    # Mock real methods from QSimGrpcClient
    client.send_command = AsyncMock(
        return_value={
            "success": True,
            "message": "Simulation started",
            "command": "start",
            "timestamp": "2023-01-01T12:00:00Z",
            "sim_state": {"running": True, "paused": False, "speed": 1.0, "fsm_state": "RUNNING"},
        }
    )

    client.health_check = AsyncMock(
        return_value={"status": "OK", "message": "Service is healthy", "timestamp": "2023-01-01T12:00:00Z"}
    )

    client.get_simulation_state = MagicMock(
        return_value={"running": True, "paused": False, "speed": 1.0, "last_health_check": None, "fsm_state": "RUNNING"}
    )

    client.set_simulation_speed = AsyncMock(
        return_value={"success": True, "speed": 2.0, "message": "Speed set to 2.0x"}
    )

    return client


@pytest.fixture
def mock_chat_client():
    """Create a mock chat gRPC client."""
    client = QAgentGrpcClient("localhost", 50052)
    client.connected = True

    # Mock real methods from QAgentGrpcClient
    client.send_message = AsyncMock(return_value="Hello! System is operational. How can I help you?")

    client.get_fsm_state = AsyncMock(
        return_value={
            "current_state": "OPERATIONAL",
            "previous_state": "INIT",
            "transitions_count": 5,
            "last_transition": "2023-01-01T12:00:00Z",
        }
    )

    client.get_proposals = AsyncMock(
        return_value=[
            {
                "id": "prop_001",
                "action": "start_simulation",
                "description": "Start simulation with default parameters",
                "confidence": 0.95,
            },
            {
                "id": "prop_002",
                "action": "check_system_status",
                "description": "Perform system health check",
                "confidence": 0.85,
            },
        ]
    )

    return client


@pytest.fixture
def mock_nats_client():
    """Create a mock NATS client."""
    client = MagicMock()
    client.is_connected = True
    client.messages_received = 150
    client.messages_processed = 145
    client.subjects = ["sim.commands", "sim.status", "chat.messages"]

    # Async methods
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.publish = AsyncMock()
    client.subscribe = AsyncMock()

    return client


@pytest.fixture
def sample_i18n():
    """Create I18n instance with sample translations."""
    return I18n(language="en")


@pytest.fixture
def sample_i18n_ru():
    """Create I18n instance with Russian translations."""
    return I18n(language="ru")


@pytest.fixture
def mock_textual_app():
    """Create a mock Textual app for widget testing."""
    from textual.app import App

    class MockApp(App):
        def __init__(self):
            super().__init__()
            self.metrics_client = None
            self.simulation_client = None
            self.chat_client = None
            self.nats_client = None
            self.i18n = I18n()

    return MockApp()


@pytest.fixture
def sample_simulation_data():
    """Sample simulation data for testing."""
    return {
        "simulations": [
            {
                "simulation_id": "sim_001",
                "scenario": "test_scenario_1",
                "status": "RUNNING",
                "progress": 45.5,
                "start_time": "2023-01-01T12:00:00Z",
                "parameters": {"duration": 300, "agents": 10, "environment": "urban"},
            },
            {
                "simulation_id": "sim_002",
                "scenario": "test_scenario_2",
                "status": "COMPLETED",
                "progress": 100.0,
                "start_time": "2023-01-01T11:00:00Z",
                "end_time": "2023-01-01T11:15:00Z",
                "parameters": {"duration": 900, "agents": 25, "environment": "highway"},
            },
        ]
    }


@pytest.fixture
def sample_chat_data():
    """Sample chat data for testing."""
    return {
        "sessions": [
            {
                "session_id": "session_001",
                "user_id": "operator_001",
                "created_at": "2023-01-01T10:00:00Z",
                "last_message_at": "2023-01-01T12:30:00Z",
                "message_count": 15,
            },
            {
                "session_id": "session_002",
                "user_id": "operator_002",
                "created_at": "2023-01-01T09:00:00Z",
                "last_message_at": "2023-01-01T11:45:00Z",
                "message_count": 8,
            },
        ],
        "messages": [
            {
                "message_id": "msg_001",
                "session_id": "session_001",
                "sender_id": "operator_001",
                "content": "Start simulation scenario_alpha",
                "timestamp": "2023-01-01T12:00:00Z",
                "type": "command",
            },
            {
                "message_id": "msg_002",
                "session_id": "session_001",
                "sender_id": "agent",
                "content": "Simulation scenario_alpha has been started with ID sim_alpha_001",
                "timestamp": "2023-01-01T12:00:15Z",
                "type": "response",
            },
            {
                "message_id": "msg_003",
                "session_id": "session_001",
                "sender_id": "operator_001",
                "content": "What is the current status?",
                "timestamp": "2023-01-01T12:30:00Z",
                "type": "question",
            },
        ],
    }


@pytest.fixture
def sample_metrics_data():
    """Sample metrics data for testing."""
    base_time = datetime.now()

    return {
        "system": {
            "cpu_usage": [{"timestamp": base_time + timedelta(seconds=i), "value": 50.0 + i * 2.5} for i in range(20)],
            "memory_usage": [
                {"timestamp": base_time + timedelta(seconds=i), "value": 65.0 + i * 1.2} for i in range(20)
            ],
            "disk_usage": [{"timestamp": base_time + timedelta(seconds=i), "value": 75.0 + (i % 5)} for i in range(20)],
        },
        "application": {
            "uptime": 3600,  # 1 hour
            "active_connections": 5,
            "processed_commands": 150,
            "error_count": 2,
        },
        "grpc": {
            "simulation_service": {"status": "connected", "requests_sent": 25, "responses_received": 24, "errors": 1},
            "chat_service": {"status": "connected", "requests_sent": 45, "responses_received": 45, "errors": 0},
        },
    }


# Async test utilities
@pytest.fixture
async def async_context():
    """Provide async context for tests."""
    yield


def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Add custom markers
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "grpc: mark test as gRPC related")
    config.addinivalue_line("markers", "ui: mark test as UI/widget test")
    config.addinivalue_line("markers", "i18n: mark test as i18n related")
    config.addinivalue_line("markers", "metrics: mark test as metrics related")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Auto-mark tests based on filename/path
        if "test_grpc" in str(item.fspath):
            item.add_marker(pytest.mark.grpc)
        if "test_i18n" in str(item.fspath):
            item.add_marker(pytest.mark.i18n)
        if "test_metrics" in str(item.fspath):
            item.add_marker(pytest.mark.metrics)
        if "widget" in str(item.fspath) or "panel" in str(item.fspath):
            item.add_marker(pytest.mark.ui)

        # Mark async tests
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
