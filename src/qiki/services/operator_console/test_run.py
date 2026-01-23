#!/usr/bin/env python3
"""
Test runner for Operator Console in Docker.

Simple script to test if the environment is set up correctly.
"""

import sys
import os


def test_imports():
    """Test if all required packages can be imported."""
    print("Testing imports...")
    
    try:
        import rich
        _ = rich.__name__
        print("✅ Rich imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import Rich: {e}")
        return False
        
    try:
        import textual
        _ = textual.__version__ if hasattr(textual, "__version__") else str(textual)
        print("✅ Textual imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import Textual: {e}")
        return False
        
    try:
        import nats
        _ = nats.__version__ if hasattr(nats, "__version__") else str(nats)
        print("✅ NATS client imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import NATS: {e}")
        return False
        
    try:
        import grpc
        _ = grpc.__version__ if hasattr(grpc, "__version__") else str(grpc)
        print("✅ gRPC imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import gRPC: {e}")
        return False
        
    return True


def test_environment():
    """Test environment variables."""
    print("\nTesting environment variables...")
    
    nats_url = os.getenv("NATS_URL", "Not set")
    grpc_host = os.getenv("GRPC_HOST", "Not set")
    grpc_port = os.getenv("GRPC_PORT", "Not set")
    
    print(f"NATS_URL: {nats_url}")
    print(f"GRPC_HOST: {grpc_host}")
    print(f"GRPC_PORT: {grpc_port}")
    
    return True


def main():
    """Main test function."""
    print("=" * 50)
    print("QIKI Operator Console - Docker Environment Test")
    print("=" * 50)
    
    if not test_imports():
        sys.exit(1)
        
    if not test_environment():
        sys.exit(1)
        
    print("\n✅ All tests passed! Environment is ready.")
    print("\nYou can now run the main application:")
    print("  python main_orion.py")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
