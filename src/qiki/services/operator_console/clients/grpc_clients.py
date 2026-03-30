"""Compatibility wrapper for gRPC clients.

Provides explicit re-exports from ``grpc_client`` to avoid wildcard imports.
"""

from .grpc_client import QAgentGrpcClient, QSimGrpcClient

SimulationGrpcClient = QSimGrpcClient
ChatGrpcClient = QAgentGrpcClient


def create_simulation_client(address: str, secure: bool = False) -> SimulationGrpcClient:
    """
    Factory function to create simulation client.

    Args:
        address: Server address (host:port)
        secure: Whether to use secure connection

    Returns:
        SimulationGrpcClient instance
    """
    if ":" in address:
        host, port = address.split(":", 1)
        return SimulationGrpcClient(host=host, port=int(port))
    return SimulationGrpcClient(host=address)


def create_chat_client(address: str, secure: bool = False) -> ChatGrpcClient:
    """
    Factory function to create chat client.

    Args:
        address: Server address (host:port)
        secure: Whether to use secure connection

    Returns:
        ChatGrpcClient instance
    """
    if ":" in address:
        host, port = address.split(":", 1)
        return ChatGrpcClient(host=host, port=int(port))
    return ChatGrpcClient(host=address)
