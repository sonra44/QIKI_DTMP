"""
gRPC Client for Operator Console.

Handles communication with Q-Sim Service and Q-Core Agent.
"""

import asyncio
import os
from typing import Optional, Dict, Any
from datetime import datetime
import logging

import grpc
from grpc import aio


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimulationCommand:
    """Simulation control commands."""
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    RESET = "reset"
    STEP = "step"


class QSimGrpcClient:
    """gRPC client for Q-Sim Service interaction."""
    
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        """
        Initialize gRPC client.
        
        Args:
            host: gRPC server host
            port: gRPC server port
        """
        # In Docker, use service names from docker-compose
        self.host = host or os.getenv("QSIM_GRPC_HOST", os.getenv("GRPC_HOST", "q-sim-service"))
        self.port = port or int(os.getenv("QSIM_GRPC_PORT", os.getenv("GRPC_PORT", "50051")))
        self.channel: Optional[aio.Channel] = None
        self.stub = None
        self.connected = False
        
        # Simulation state
        self.sim_state: Dict[str, Any] = {
            "running": False,
            "paused": False,
            "speed": 1.0,
            "last_health_check": None,
            "fsm_state": "UNKNOWN"
        }
        
    async def connect(self) -> bool:
        """
        Connect to gRPC server.
        
        Returns:
            True if connection successful
        """
        try:
            # Create channel
            target = f"{self.host}:{self.port}"
            self.channel = aio.insecure_channel(
                target,
                options=[
                    ('grpc.keepalive_time_ms', 10000),
                    ('grpc.keepalive_timeout_ms', 5000),
                    ('grpc.keepalive_permit_without_calls', True),
                    ('grpc.http2.max_pings_without_data', 0),
                ]
            )
            
            # Wait for channel to be ready
            await self.channel.channel_ready()
            
            self.connected = True
            logger.info(f"✅ Connected to gRPC server at {target}")
            
            # Perform initial health check
            await self.health_check()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to gRPC server: {e}")
            self.connected = False
            return False
            
    async def disconnect(self) -> None:
        """Disconnect from gRPC server."""
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.connected = False
            logger.info("Disconnected from gRPC server")
            
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the service.
        
        Returns:
            Health check result
        """
        if not self.connected or not self.channel:
            return {"status": "ERROR", "message": "Not connected"}
            
        try:
            # Create a simple health check request
            # Since we don't have generated stubs, we'll use a basic approach
            
            # For now, we'll just check if the channel is ready
            state = self.channel.get_state()
            
            # grpc.ChannelConnectivity.READY has value 1
            if state == grpc.ChannelConnectivity.READY or state == 1:
                result = {
                    "status": "OK",
                    "message": "Service is healthy",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                result = {
                    "status": "ERROR",
                    "message": f"Channel state: {state}",
                    "timestamp": datetime.now().isoformat()
                }
                
            self.sim_state["last_health_check"] = result
            return result
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "ERROR",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
    async def send_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send a command to the simulation.
        
        Args:
            command: Command type (start, stop, pause, etc.)
            params: Optional command parameters
            
        Returns:
            Command response
        """
        if not self.connected:
            return {"success": False, "message": "Not connected to gRPC server"}
            
        try:
            # No-mocks: Operator Console управляет симуляцией через NATS control plane.
            # Этот gRPC клиент пока используется только для health-check уровня канала.
            return {
                "success": False,
                "message": "Not implemented: use NATS control commands (qiki.commands.control)",
                "command": command,
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            return {
                "success": False,
                "message": str(e),
                "command": command
            }
            
    async def get_sensor_data(self) -> Dict[str, Any]:
        """
        Get current sensor data from simulation.
        
        Returns:
            Sensor data dictionary
        """
        if not self.connected:
            return {"error": "Not connected"}
            
        try:
            return {"error": "Not implemented (no stubs wired for Operator Console)"}
            
        except Exception as e:
            logger.error(f"Failed to get sensor data: {e}")
            return {"error": str(e)}
            
    async def get_radar_frame(self) -> Dict[str, Any]:
        """
        Get current radar frame from simulation.
        
        Returns:
            Radar frame data
        """
        if not self.connected:
            return {"error": "Not connected"}
            
        try:
            return {"error": "Not implemented (no stubs wired for Operator Console)"}
            
        except Exception as e:
            logger.error(f"Failed to get radar frame: {e}")
            return {"error": str(e)}
            
    async def send_actuator_command(self, command_type: str, value: float) -> Dict[str, Any]:
        """
        Send actuator command to simulation.
        
        Args:
            command_type: Type of actuator (thrust, steering, etc.)
            value: Command value
            
        Returns:
            Command response
        """
        if not self.connected:
            return {"success": False, "message": "Not connected"}
            
        try:
            return {
                "success": False,
                "message": "Not implemented (no stubs wired for Operator Console)",
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to send actuator command: {e}")
            return {
                "success": False,
                "message": str(e)
            }
            
    def get_simulation_state(self) -> Dict[str, Any]:
        """
        Get current simulation state.
        
        Returns:
            Current simulation state
        """
        return self.sim_state.copy()
        
    async def set_simulation_speed(self, speed: float) -> Dict[str, Any]:
        """
        Set simulation speed multiplier.
        
        Args:
            speed: Speed multiplier (1.0 = normal, 2.0 = 2x, etc.)
            
        Returns:
            Command response
        """
        if not self.connected:
            return {"success": False, "message": "Not connected"}
            
        try:
            return {
                "success": False,
                "message": "Not implemented: use NATS control commands (qiki.commands.control)",
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }


# Agent interaction client
class QAgentGrpcClient:
    """gRPC client for Q-Core Agent interaction."""
    
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        """Initialize agent client."""
        # In Docker, use service names from docker-compose
        self.host = host or os.getenv("AGENT_GRPC_HOST", "q-core-agent")
        self.port = port or int(os.getenv("AGENT_GRPC_PORT", "50052"))
        self.channel: Optional[aio.Channel] = None
        self.connected = False
        
    async def connect(self) -> bool:
        """Connect to Q-Core Agent."""
        try:
            target = f"{self.host}:{self.port}"
            self.channel = aio.insecure_channel(target)
            await asyncio.wait_for(self.channel.channel_ready(), timeout=2.0)
            self.connected = True
            logger.info(f"✅ Connected to Q-Core Agent channel at {target}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Q-Core Agent: {e}")
            self.connected = False
            self.channel = None
            return False
        
    async def send_message(self, message: str) -> str:
        """
        Send natural language message to agent.
        
        Args:
            message: Natural language command or query
            
        Returns:
            Agent's response
        """
        if not self.connected:
            return "Error: Not connected to agent"

        # No-mocks: пока нет зафиксированного gRPC контракта для чат-интерфейса Q-Core Agent.
        logger.info("Agent chat requested but RPC is not wired: %s", message)
        return "Error: Agent chat RPC not implemented (no stubs wired)"
            
    async def get_fsm_state(self) -> Dict[str, Any]:
        """
        Get current FSM state from agent.
        
        Returns:
            FSM state information
        """
        return {"error": "Not implemented (no stubs wired)"}
        
    async def get_proposals(self) -> list:
        """
        Get current action proposals from agent.
        
        Returns:
            List of proposals
        """
        return []


# Test function
async def test_grpc_clients():
    """Test gRPC clients."""
    # Test Q-Sim client
    sim_client = QSimGrpcClient()
    
    print("Testing Q-Sim gRPC Client...")
    if await sim_client.connect():
        # Health check
        health = await sim_client.health_check()
        print(f"Health: {health}")
        
        # Send commands
        result = await sim_client.send_command(SimulationCommand.START)
        print(f"Start command: {result}")
        
        # Get sensor data
        sensor_data = await sim_client.get_sensor_data()
        print(f"Sensor data: {sensor_data}")
        
        await sim_client.disconnect()
        
    # Test Agent client
    agent_client = QAgentGrpcClient()
    
    print("\nTesting Q-Agent gRPC Client...")
    if await agent_client.connect():
        # Send message
        response = await agent_client.send_message("What is the system status?")
        print(f"Agent response: {response}")
        
        # Get FSM state
        fsm = await agent_client.get_fsm_state()
        print(f"FSM State: {fsm}")
        
        # Get proposals
        proposals = await agent_client.get_proposals()
        print(f"Proposals: {proposals}")


if __name__ == "__main__":
    asyncio.run(test_grpc_clients())
