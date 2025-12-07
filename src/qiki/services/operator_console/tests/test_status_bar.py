"""
Tests for StatusBar widget.
"""

import pytest
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.status_bar import StatusBar, ConnectionStatus


class TestConnectionStatus:
    """Test ConnectionStatus constants."""
    
    def test_status_values(self):
        """Test status indicator values."""
        assert ConnectionStatus.CONNECTED == "🟢"
        assert ConnectionStatus.DISCONNECTED == "🔴"
        assert ConnectionStatus.CONNECTING == "🟡"
        assert ConnectionStatus.ERROR == "❌"


class TestStatusBar:
    """Test StatusBar widget."""
    
    @pytest.fixture
    def status_bar(self):
        """Create StatusBar instance."""
        return StatusBar()
    
    def test_initialization(self, status_bar):
        """Test StatusBar initializes with correct defaults."""
        assert status_bar.nats_status == "🔴"
        assert status_bar.sim_grpc_status == "🔴"
        assert status_bar.agent_grpc_status == "🔴"
        
        assert status_bar.connection_states["nats"] == ConnectionStatus.DISCONNECTED
        assert status_bar.connection_states["sim_grpc"] == ConnectionStatus.DISCONNECTED
        assert status_bar.connection_states["agent_grpc"] == ConnectionStatus.DISCONNECTED
    
    def test_update_connection_connected(self, status_bar):
        """Test updating connection to connected state."""
        status_bar.update_connection("nats", connected=True)
        
        assert status_bar.nats_status == ConnectionStatus.CONNECTED
        assert status_bar.connection_states["nats"] == ConnectionStatus.CONNECTED
    
    def test_update_connection_disconnected(self, status_bar):
        """Test updating connection to disconnected state."""
        # First connect
        status_bar.update_connection("sim_grpc", connected=True)
        assert status_bar.sim_grpc_status == ConnectionStatus.CONNECTED
        
        # Then disconnect
        status_bar.update_connection("sim_grpc", connected=False)
        assert status_bar.sim_grpc_status == ConnectionStatus.DISCONNECTED
    
    def test_update_connection_error(self, status_bar):
        """Test updating connection to error state."""
        status_bar.update_connection("agent_grpc", connected=False, error=True)
        
        assert status_bar.agent_grpc_status == ConnectionStatus.ERROR
        assert status_bar.connection_states["agent_grpc"] == ConnectionStatus.ERROR
    
    def test_set_connecting(self, status_bar):
        """Test setting connection to connecting state."""
        status_bar.set_connecting("nats")
        
        assert status_bar.nats_status == ConnectionStatus.CONNECTING
        assert status_bar.connection_states["nats"] == ConnectionStatus.CONNECTING
    
    def test_set_connecting_all_services(self, status_bar):
        """Test setting all services to connecting state."""
        status_bar.set_connecting("nats")
        status_bar.set_connecting("sim_grpc")
        status_bar.set_connecting("agent_grpc")
        
        assert status_bar.nats_status == ConnectionStatus.CONNECTING
        assert status_bar.sim_grpc_status == ConnectionStatus.CONNECTING
        assert status_bar.agent_grpc_status == ConnectionStatus.CONNECTING
    
    def test_render(self, status_bar):
        """Test rendering status bar."""
        
        # Set some states
        status_bar.update_connection("nats", connected=True)
        status_bar.update_connection("sim_grpc", connected=False, error=True)
        status_bar.set_connecting("agent_grpc")
        
        # Render
        rendered = status_bar.render()
        text = str(rendered)
        
        # Check components are present
        assert "NATS: 🟢" in text
        assert "Q-Sim: ❌" in text
        assert "Q-Agent: 🟡" in text
        # Time is present but we don't check exact value
        assert "⏰" in text
    
    def test_get_health_summary(self, status_bar):
        """Test getting health summary."""
        # Set different states
        status_bar.update_connection("nats", connected=True)
        status_bar.update_connection("sim_grpc", connected=False)
        status_bar.set_connecting("agent_grpc")
        
        summary = status_bar.get_health_summary()
        
        assert summary["nats"] == "Connected"
        assert summary["sim_grpc"] == "Disconnected"
        assert summary["agent_grpc"] == "Connecting"
    
    def test_status_to_text(self, status_bar):
        """Test status emoji to text conversion."""
        assert status_bar._status_to_text(ConnectionStatus.CONNECTED) == "Connected"
        assert status_bar._status_to_text(ConnectionStatus.DISCONNECTED) == "Disconnected"
        assert status_bar._status_to_text(ConnectionStatus.CONNECTING) == "Connecting"
        assert status_bar._status_to_text(ConnectionStatus.ERROR) == "Error"
        assert status_bar._status_to_text("unknown") == "Unknown"
    
    def test_multiple_state_changes(self, status_bar):
        """Test multiple state changes."""
        # Initial state
        assert status_bar.nats_status == ConnectionStatus.DISCONNECTED
        
        # Connecting
        status_bar.set_connecting("nats")
        assert status_bar.nats_status == ConnectionStatus.CONNECTING
        
        # Connected
        status_bar.update_connection("nats", connected=True)
        assert status_bar.nats_status == ConnectionStatus.CONNECTED
        
        # Error
        status_bar.update_connection("nats", connected=False, error=True)
        assert status_bar.nats_status == ConnectionStatus.ERROR
        
        # Disconnected
        status_bar.update_connection("nats", connected=False)
        assert status_bar.nats_status == ConnectionStatus.DISCONNECTED
    
    def test_all_services_connected(self, status_bar):
        """Test all services connected state."""
        status_bar.update_connection("nats", connected=True)
        status_bar.update_connection("sim_grpc", connected=True)
        status_bar.update_connection("agent_grpc", connected=True)
        
        assert status_bar.nats_status == ConnectionStatus.CONNECTED
        assert status_bar.sim_grpc_status == ConnectionStatus.CONNECTED
        assert status_bar.agent_grpc_status == ConnectionStatus.CONNECTED
        
        summary = status_bar.get_health_summary()
        assert all(status == "Connected" for status in summary.values())
    
    def test_all_services_error(self, status_bar):
        """Test all services in error state."""
        status_bar.update_connection("nats", connected=False, error=True)
        status_bar.update_connection("sim_grpc", connected=False, error=True)
        status_bar.update_connection("agent_grpc", connected=False, error=True)
        
        assert status_bar.nats_status == ConnectionStatus.ERROR
        assert status_bar.sim_grpc_status == ConnectionStatus.ERROR
        assert status_bar.agent_grpc_status == ConnectionStatus.ERROR
        
        summary = status_bar.get_health_summary()
        assert all(status == "Error" for status in summary.values())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
