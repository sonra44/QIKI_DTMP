#!/bin/bash

# Скрипт для запуска Q-Core Agent с поддержкой gRPC

echo "Starting Q-Core Agent with gRPC support..."

# Переходим в корневую директорию проекта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Добавляем src/ в PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT"

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed or not in PATH"
    exit 1
fi

# Проверяем наличие зависимостей
if ! python3 -c "import grpc" 2>/dev/null; then
    echo "Error: gRPC is not installed. Run: pip install grpcio grpcio-tools"
    exit 1
fi

# Генерируем protobuf файлы если нужно
if [ ! -f "generated/q_sim_api_pb2.py" ]; then
    echo "Generating protobuf files..."
    python3 -m grpc_tools.protoc \
        --proto_path=protos \
        --python_out=generated \
        --grpc_python_out=generated \
        protos/q_sim_api.proto
fi

# Проверяем доступность симулятора
echo "Checking Q-Sim Server availability..."
# shellcheck disable=SC2016
if ! python3 -c "
import grpc
from generated.q_sim_api_pb2_grpc import QSimAPIServiceStub
from generated.q_sim_api_pb2 import HealthCheckRequest
try:
    channel = grpc.insecure_channel('localhost:50051')
    stub = QSimAPIServiceStub(channel)
    response = stub.HealthCheck(HealthCheckRequest(), timeout=3.0)
    print(f'Q-Sim Server is available: {response.message}')
    channel.close()
except Exception as e:
    print(f'Q-Sim Server is not available: {e}')
    exit(1)
"; then
    echo "Q-Sim Server is ready!"
else
    echo "Error: Q-Sim Server is not running. Please start it first with ./scripts/start_sim.sh"
    exit 1
fi

# Запускаем агента в режиме gRPC
echo "Launching Q-Core Agent with gRPC..."
python3 -m qiki.services.q_core_agent.main --grpc

echo "Q-Core Agent stopped."
