"""
Status Bar Widget for QIKI Operator Console.
Shows connection status for NATS, gRPC services.
"""

from textual.widgets import Static
from textual.reactive import reactive
from rich.console import RenderableType
from rich.text import Text
from typing import Dict


class ConnectionStatus:
    """Connection status indicators."""
    CONNECTED = "🟢"
    DISCONNECTED = "🔴"
    CONNECTING = "🟡"
    ERROR = "❌"


class StatusBar(Static):
    """Status bar showing connection states."""
    
    nats_status = reactive("🔴")
    sim_grpc_status = reactive("🔴")
    agent_grpc_status = reactive("🔴")
    
    def __init__(self, **kwargs):
        """Initialize status bar."""
        super().__init__(**kwargs)
        self.connection_states = {
            "nats": ConnectionStatus.DISCONNECTED,
            "sim_grpc": ConnectionStatus.DISCONNECTED,
            "agent_grpc": ConnectionStatus.DISCONNECTED
        }
    
    def update_connection(self, service: str, connected: bool, error: bool = False):
        """
        Update connection status for a service.
        
        Args:
            service: Service name (nats, sim_grpc, agent_grpc)
            connected: Whether service is connected
            error: Whether there was an error
        """
        if error:
            status = ConnectionStatus.ERROR
        elif connected:
            status = ConnectionStatus.CONNECTED
        else:
            status = ConnectionStatus.DISCONNECTED
        
        self.connection_states[service] = status
        
        # Update reactive properties
        if service == "nats":
            self.nats_status = status
        elif service == "sim_grpc":
            self.sim_grpc_status = status
        elif service == "agent_grpc":
            self.agent_grpc_status = status
        
        self.refresh()
    
    def set_connecting(self, service: str):
        """Set service status to connecting."""
        self.connection_states[service] = ConnectionStatus.CONNECTING
        
        if service == "nats":
            self.nats_status = ConnectionStatus.CONNECTING
        elif service == "sim_grpc":
            self.sim_grpc_status = ConnectionStatus.CONNECTING
        elif service == "agent_grpc":
            self.agent_grpc_status = ConnectionStatus.CONNECTING
        
        self.refresh()
    
    def render(self) -> RenderableType:
        """Render status bar."""
        text = Text()
        
        # NATS Status
        text.append(f" NATS: {self.nats_status} ")
        text.append(" │ ", style="dim")
        
        # Q-Sim gRPC Status
        text.append(f"Q-Sim: {self.sim_grpc_status} ")
        text.append(" │ ", style="dim")
        
        # Q-Agent gRPC Status  
        text.append(f"Q-Agent: {self.agent_grpc_status} ")
        
        # Add timestamp
        from datetime import datetime
        now = datetime.now().strftime("%H:%M:%S")
        text.append(" │ ", style="dim")
        text.append(f"⏰ {now}", style="dim")
        
        return text
    
    def get_health_summary(self) -> Dict[str, str]:
        """Get health summary of all connections."""
        return {
            "nats": self._status_to_text(self.nats_status),
            "sim_grpc": self._status_to_text(self.sim_grpc_status),
            "agent_grpc": self._status_to_text(self.agent_grpc_status)
        }
    
    def _status_to_text(self, status: str) -> str:
        """Convert status emoji to text."""
        mapping = {
            ConnectionStatus.CONNECTED: "Connected",
            ConnectionStatus.DISCONNECTED: "Disconnected",
            ConnectionStatus.CONNECTING: "Connecting",
            ConnectionStatus.ERROR: "Error"
        }
        return mapping.get(status, "Unknown")
