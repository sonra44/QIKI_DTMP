#!/bin/bash

# Скрипт для запуска Q-Sim Service в режиме gRPC сервера

echo "Starting Q-Sim gRPC Server..."

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

# Запускаем gRPC сервер симулятора
echo "Launching Q-Sim gRPC Server..."
python3 -m qiki.services.q_sim_service.grpc_server

echo "Q-Sim Server stopped."
