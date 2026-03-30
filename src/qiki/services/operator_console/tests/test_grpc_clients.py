"""
Tests for gRPC clients functionality.
"""

import pytest
import grpc
from unittest.mock import MagicMock, AsyncMock, patch

from qiki.services.operator_console.clients.grpc_client import QSimGrpcClient, QAgentGrpcClient, SimulationCommand


class TestQSimGrpcClient:
    """Test QSimGrpcClient functionality."""

    @pytest.fixture
    def client(self):
        """Create test simulation client."""
        return QSimGrpcClient("localhost", 50051)

    def test_client_initialization(self, client):
        """Test client initializes correctly."""
        assert client.host == "localhost"
        assert client.port == 50051
        assert not client.connected
        assert client.channel is None
        assert client.stub is None
        assert "running" in client.sim_state
        assert "paused" in client.sim_state

    @pytest.mark.asyncio
    async def test_connect_success(self, client):
        """Test successful connection."""
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_channel_instance = AsyncMock()
            mock_channel_instance.channel_ready = AsyncMock()
            mock_channel_instance.get_state = MagicMock(return_value=grpc.ChannelConnectivity.READY)
            mock_channel.return_value = mock_channel_instance

            result = await client.connect()

            assert result is True
            assert client.connected
            assert client.channel is mock_channel_instance
            mock_channel.assert_called_once_with(
                "localhost:50051",
                options=[
                    ("grpc.keepalive_time_ms", 10000),
                    ("grpc.keepalive_timeout_ms", 5000),
                    ("grpc.keepalive_permit_without_calls", True),
                    ("grpc.http2.max_pings_without_data", 0),
                ],
            )

    @pytest.mark.asyncio
    async def test_connect_failure(self, client):
        """Test connection failure."""
        with patch("grpc.aio.insecure_channel", side_effect=Exception("Connection failed")):
            result = await client.connect()

            assert result is False
            assert not client.connected
            assert client.channel is None
            assert client.stub is None

    @pytest.mark.asyncio
    async def test_disconnect(self, client):
        """Test disconnection."""
        # Set up connected state
        mock_channel = AsyncMock()
        client.channel = mock_channel
        client.connected = True

        await client.disconnect()

        assert not client.connected
        assert client.channel is None
        mock_channel.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_connected(self, client):
        """Test health check when connected."""
        mock_channel = MagicMock()
        mock_channel.get_state.return_value = grpc.ChannelConnectivity.READY

        client.connected = True
        client.channel = mock_channel

        result = await client.health_check()

        assert result["status"] == "OK"
        assert "Service is healthy" in result["message"]
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_health_check_disconnected(self, client):
        """Test health check when disconnected."""
        result = await client.health_check()
        assert result["status"] == "ERROR"
        assert "Not connected" in result["message"]

    @pytest.mark.asyncio
    async def test_health_check_exception(self, client):
        """Test health check with exception."""
        mock_channel = MagicMock()
        mock_channel.get_state.side_effect = Exception("Channel error")

        client.connected = True
        client.channel = mock_channel

        result = await client.health_check()
        assert result["status"] == "ERROR"
        assert "Channel error" in result["message"]

    @pytest.mark.asyncio
    async def test_send_command_start(self, client):
        """Test sending start command (not implemented; no-mocks)."""
        client.connected = True

        result = await client.send_command(SimulationCommand.START)

        assert result["success"] is False
        assert "Not implemented" in result["message"]
        assert result["command"] == "start"

    @pytest.mark.asyncio
    async def test_send_command_disconnected(self, client):
        """Test sending command when disconnected."""
        result = await client.send_command(SimulationCommand.START)

        assert result["success"] is False
        assert "Not connected" in result["message"]

    @pytest.mark.asyncio
    async def test_send_command_stop(self, client):
        """Test stopping simulation (not implemented; no-mocks)."""
        client.connected = True
        client.sim_state["running"] = True  # Set initial state

        result = await client.send_command(SimulationCommand.STOP)

        assert result["success"] is False
        assert "Not implemented" in result["message"]

    @pytest.mark.asyncio
    async def test_send_command_pause(self, client):
        """Test pausing simulation (not implemented; no-mocks)."""
        client.connected = True
        client.sim_state["running"] = True

        result = await client.send_command(SimulationCommand.PAUSE)

        assert result["success"] is False
        assert "Not implemented" in result["message"]

    @pytest.mark.asyncio
    async def test_get_simulation_state(self, client):
        """Test getting simulation state."""
        client.sim_state["running"] = True
        client.sim_state["paused"] = False
        client.sim_state["speed"] = 2.0

        result = client.get_simulation_state()

        assert result["running"] is True
        assert result["paused"] is False
        assert result["speed"] == 2.0

    @pytest.mark.asyncio
    async def test_set_simulation_speed(self, client):
        """Test setting simulation speed (not implemented; no-mocks)."""
        client.connected = True

        result = await client.set_simulation_speed(2.5)

        assert result["success"] is False
        assert "Not implemented" in result["message"]


class TestQAgentGrpcClient:
    """Test QAgentGrpcClient functionality."""

    @pytest.fixture
    def agent_client(self):
        """Create test agent client."""
        return QAgentGrpcClient("localhost", 50052)

    def test_agent_client_initialization(self, agent_client):
        """Test agent client initializes correctly."""
        assert agent_client.host == "localhost"
        assert agent_client.port == 50052
        assert not agent_client.connected

    @pytest.mark.asyncio
    async def test_agent_connect(self, agent_client):
        """Test agent connection."""
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_channel_instance = AsyncMock()
            mock_channel_instance.channel_ready = AsyncMock()
            mock_channel.return_value = mock_channel_instance

            result = await agent_client.connect()

            assert result is True
            assert agent_client.connected is True

    @pytest.mark.asyncio
    async def test_send_message_connected(self, agent_client):
        """Test sending message when connected (RPC not implemented)."""
        agent_client.connected = True

        result = await agent_client.send_message("What is the system status?")

        assert "not implemented" in result.lower()

    @pytest.mark.asyncio
    async def test_send_message_disconnected(self, agent_client):
        """Test sending message when disconnected."""
        result = await agent_client.send_message("Hello")

        assert "Error: Not connected" in result

    @pytest.mark.asyncio
    async def test_get_fsm_state(self, agent_client):
        """Test getting FSM state."""
        result = await agent_client.get_fsm_state()

        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_proposals(self, agent_client):
        """Test getting proposals."""
        result = await agent_client.get_proposals()

        assert isinstance(result, list)
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
