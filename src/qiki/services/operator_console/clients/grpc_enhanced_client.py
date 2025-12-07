"""
Enhanced gRPC Client for QIKI Operator Console.
Provides async interface for simulation control and agent communication.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable
from enum import Enum
from dataclasses import dataclass
from grpc import aio

# Import protobuf definitions (these should be generated from .proto files)
# from qiki.proto import simulation_pb2, simulation_pb2_grpc
# from qiki.proto import agent_pb2, agent_pb2_grpc


logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """gRPC connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class SimulationCommand(Enum):
    """Simulation control commands."""
    START = "start"
    PAUSE = "pause"
    STOP = "stop"
    RESET = "reset"
    EXPORT = "export_telemetry"
    DIAGNOSTICS = "diagnostics"


@dataclass
class CommandResponse:
    """Response from command execution."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class ChatMessage:
    """Chat message structure."""
    text: str
    language: str = "en"
    context: Optional[Dict[str, Any]] = None


@dataclass
class ChatResponse:
    """Response from Q-Agent."""
    text: str
    language: str
    confidence: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


class EnhancedGrpcClient:
    """Enhanced gRPC client with reconnection and error handling."""
    
    def __init__(
        self,
        sim_host: str = "localhost",
        sim_port: int = 50051,
        agent_host: str = "localhost", 
        agent_port: int = 50052,
        reconnect_interval: int = 5,
        max_reconnect_attempts: int = 10
    ):
        """
        Initialize gRPC client.
        
        Args:
            sim_host: Simulation service host
            sim_port: Simulation service port
            agent_host: Q-Agent service host
            agent_port: Q-Agent service port
            reconnect_interval: Seconds between reconnection attempts
            max_reconnect_attempts: Maximum reconnection attempts
        """
        self.sim_address = f"{sim_host}:{sim_port}"
        self.agent_address = f"{agent_host}:{agent_port}"
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        
        # Channels and stubs
        self.sim_channel: Optional[aio.Channel] = None
        self.agent_channel: Optional[aio.Channel] = None
        # self.sim_stub: Optional[simulation_pb2_grpc.SimulationServiceStub] = None
        # self.agent_stub: Optional[agent_pb2_grpc.AgentServiceStub] = None
        
        # Connection state
        self.sim_state = ConnectionState.DISCONNECTED
        self.agent_state = ConnectionState.DISCONNECTED
        self.reconnect_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self.state_callbacks: Dict[str, Callable] = {}
        
    async def connect(self) -> bool:
        """
        Connect to gRPC services.
        
        Returns:
            True if both connections successful
        """
        sim_connected = await self._connect_simulation()
        agent_connected = await self._connect_agent()
        
        if not (sim_connected or agent_connected):
            # Start reconnection task if not already running
            if not self.reconnect_task or self.reconnect_task.done():
                self.reconnect_task = asyncio.create_task(self._reconnect_loop())
        
        return sim_connected and agent_connected
    
    async def _connect_simulation(self) -> bool:
        """Connect to simulation service."""
        try:
            self.sim_state = ConnectionState.CONNECTING
            self._notify_state_change("simulation", self.sim_state)
            
            # Create insecure channel
            self.sim_channel = aio.insecure_channel(
                self.sim_address,
                options=[
                    ('grpc.keepalive_time_ms', 30000),
                    ('grpc.keepalive_timeout_ms', 10000),
                    ('grpc.keepalive_permit_without_calls', True),
                ]
            )
            
            # Create stub (uncomment when proto is available)
            # self.sim_stub = simulation_pb2_grpc.SimulationServiceStub(self.sim_channel)
            
            # Test connection with a simple call
            # await self.sim_stub.GetStatus(simulation_pb2.Empty(), timeout=5)
            
            self.sim_state = ConnectionState.CONNECTED
            self._notify_state_change("simulation", self.sim_state)
            logger.info(f"Connected to simulation service at {self.sim_address}")
            return True
            
        except Exception as e:
            self.sim_state = ConnectionState.ERROR
            self._notify_state_change("simulation", self.sim_state)
            logger.error(f"Failed to connect to simulation service: {e}")
            return False
    
    async def _connect_agent(self) -> bool:
        """Connect to Q-Agent service."""
        try:
            self.agent_state = ConnectionState.CONNECTING
            self._notify_state_change("agent", self.agent_state)
            
            # Create insecure channel
            self.agent_channel = aio.insecure_channel(
                self.agent_address,
                options=[
                    ('grpc.keepalive_time_ms', 30000),
                    ('grpc.keepalive_timeout_ms', 10000),
                    ('grpc.keepalive_permit_without_calls', True),
                ]
            )
            
            # Create stub (uncomment when proto is available)
            # self.agent_stub = agent_pb2_grpc.AgentServiceStub(self.agent_channel)
            
            # Test connection
            # await self.agent_stub.GetStatus(agent_pb2.Empty(), timeout=5)
            
            self.agent_state = ConnectionState.CONNECTED
            self._notify_state_change("agent", self.agent_state)
            logger.info(f"Connected to Q-Agent service at {self.agent_address}")
            return True
            
        except Exception as e:
            self.agent_state = ConnectionState.ERROR
            self._notify_state_change("agent", self.agent_state)
            logger.error(f"Failed to connect to Q-Agent service: {e}")
            return False
    
    async def _reconnect_loop(self):
        """Automatic reconnection loop."""
        attempts = 0
        
        while attempts < self.max_reconnect_attempts:
            await asyncio.sleep(self.reconnect_interval)
            
            # Try to reconnect disconnected services
            if self.sim_state != ConnectionState.CONNECTED:
                logger.info("Attempting to reconnect to simulation service...")
                await self._connect_simulation()
            
            if self.agent_state != ConnectionState.CONNECTED:
                logger.info("Attempting to reconnect to Q-Agent service...")
                await self._connect_agent()
            
            # Check if both connected
            if (self.sim_state == ConnectionState.CONNECTED and 
                self.agent_state == ConnectionState.CONNECTED):
                logger.info("All services reconnected successfully")
                break
            
            attempts += 1
            
        if attempts >= self.max_reconnect_attempts:
            logger.error("Maximum reconnection attempts reached")
    
    async def disconnect(self):
        """Disconnect from all services."""
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
        
        if self.sim_channel:
            await self.sim_channel.close()
            self.sim_channel = None
            self.sim_state = ConnectionState.DISCONNECTED
            self._notify_state_change("simulation", self.sim_state)
        
        if self.agent_channel:
            await self.agent_channel.close()
            self.agent_channel = None
            self.agent_state = ConnectionState.DISCONNECTED
            self._notify_state_change("agent", self.agent_state)
    
    async def send_command(self, command: SimulationCommand, **kwargs) -> CommandResponse:
        """
        Send command to simulation service.
        
        Args:
            command: Command to execute
            **kwargs: Additional parameters
            
        Returns:
            CommandResponse with result
        """
        if self.sim_state != ConnectionState.CONNECTED:
            return CommandResponse(
                success=False,
                message="Not connected to simulation service",
                error="CONNECTION_ERROR"
            )
        
        try:
            # Implementation would use actual protobuf messages
            # For now, return mock response
            logger.info(f"Sending command: {command.value} with params: {kwargs}")
            
            # Simulate command execution
            await asyncio.sleep(0.1)
            
            return CommandResponse(
                success=True,
                message=f"Command {command.value} executed successfully",
                data={"command": command.value, "params": kwargs}
            )
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return CommandResponse(
                success=False,
                message=f"Command failed: {str(e)}",
                error=str(e)
            )
    
    async def start_simulation(self, scenario: Optional[str] = None) -> CommandResponse:
        """Start simulation with optional scenario."""
        return await self.send_command(SimulationCommand.START, scenario=scenario)
    
    async def pause_simulation(self) -> CommandResponse:
        """Pause running simulation."""
        return await self.send_command(SimulationCommand.PAUSE)
    
    async def stop_simulation(self) -> CommandResponse:
        """Stop simulation."""
        return await self.send_command(SimulationCommand.STOP)
    
    async def reset_simulation(self) -> CommandResponse:
        """Reset simulation to initial state."""
        return await self.send_command(SimulationCommand.RESET)
    
    async def export_telemetry(self, format: str = "json", path: Optional[str] = None) -> CommandResponse:
        """Export telemetry data."""
        return await self.send_command(SimulationCommand.EXPORT, format=format, path=path)
    
    async def run_diagnostics(self, components: Optional[list] = None) -> CommandResponse:
        """Run system diagnostics."""
        return await self.send_command(SimulationCommand.DIAGNOSTICS, components=components)
    
    async def send_chat_message(self, message: ChatMessage) -> ChatResponse:
        """
        Send message to Q-Agent.
        
        Args:
            message: Chat message to send
            
        Returns:
            ChatResponse from agent
        """
        if self.agent_state != ConnectionState.CONNECTED:
            return ChatResponse(
                text="Error: Not connected to Q-Agent service",
                language=message.language,
                confidence=0.0,
                metadata={"error": "CONNECTION_ERROR"}
            )
        
        try:
            logger.info(f"Sending chat message: {message.text[:50]}...")
            
            # Implementation would use actual protobuf messages
            # For now, return mock response
            await asyncio.sleep(0.2)  # Simulate processing
            
            return ChatResponse(
                text=f"Received and processed: {message.text}",
                language=message.language,
                confidence=0.95,
                metadata={"processed": True, "tokens": len(message.text.split())}
            )
            
        except Exception as e:
            logger.error(f"Chat message failed: {e}")
            return ChatResponse(
                text=f"Error: {str(e)}",
                language=message.language,
                confidence=0.0,
                metadata={"error": str(e)}
            )
    
    async def get_simulation_status(self) -> Dict[str, Any]:
        """Get current simulation status."""
        if self.sim_state != ConnectionState.CONNECTED:
            return {"status": "disconnected", "error": "Not connected"}
        
        try:
            # Would call actual gRPC method
            return {
                "status": "running",
                "scenario": "default",
                "time_elapsed": 1234.5,
                "entities": 5
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def get_agent_status(self) -> Dict[str, Any]:
        """Get Q-Agent status."""
        if self.agent_state != ConnectionState.CONNECTED:
            return {"status": "disconnected", "error": "Not connected"}
        
        try:
            # Would call actual gRPC method
            return {
                "status": "active",
                "model": "QIKI-v2",
                "conversations": 3,
                "avg_response_time": 0.25
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def register_state_callback(self, service: str, callback: Callable):
        """Register callback for connection state changes."""
        self.state_callbacks[service] = callback
    
    def _notify_state_change(self, service: str, state: ConnectionState):
        """Notify registered callbacks about state change."""
        if service in self.state_callbacks:
            try:
                self.state_callbacks[service](state)
            except Exception as e:
                logger.error(f"State callback error: {e}")
    
    def get_connection_states(self) -> Dict[str, ConnectionState]:
        """Get current connection states."""
        return {
            "simulation": self.sim_state,
            "agent": self.agent_state
        }


# Example usage
async def main():
    """Example usage of enhanced gRPC client."""
    client = EnhancedGrpcClient()
    
    # Register state change callback
    def on_state_change(state):
        print(f"State changed: {state}")
    
    client.register_state_callback("simulation", on_state_change)
    client.register_state_callback("agent", on_state_change)
    
    # Connect
    await client.connect()
    
    # Send commands
    response = await client.start_simulation("test_scenario")
    print(f"Start response: {response}")
    
    # Send chat message
    msg = ChatMessage(text="Hello Q-Agent", language="en")
    chat_response = await client.send_chat_message(msg)
    print(f"Chat response: {chat_response}")
    
    # Get status
    sim_status = await client.get_simulation_status()
    print(f"Simulation status: {sim_status}")
    
    # Disconnect
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
