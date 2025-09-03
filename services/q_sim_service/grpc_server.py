import grpc
import time
import signal
import sys
import os
from concurrent import futures
from typing import Dict, Any

# Добавляем корневую директорию проекта в sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(ROOT_DIR)

from services.q_sim_service.logger import setup_logging, logger
from services.q_sim_service.main import QSimService
from generated.q_sim_api_pb2_grpc import QSimAPIServicer, add_QSimAPIServicer_to_server
from generated.q_sim_api_pb2 import HealthResponse
from google.protobuf.empty_pb2 import Empty


class QSimGrpcServicer(QSimAPIServicer):
    """
    gRPC сервис для взаимодействия с Q-Sim Service.
    Предоставляет методы получения данных сенсоров и отправки команд актуаторам.
    """
    
    def __init__(self, qsim_service: QSimService):
        self.qsim_service = qsim_service
        logger.info("QSimGrpcServicer initialized")
    
    def GetSensorData(self, request, context):
        """Возвращает данные сенсоров"""
        try:
            sensor_data = self.qsim_service.generate_sensor_data()
            logger.debug(f"Returning sensor data via gRPC: {sensor_data.sensor_id.value}")
            return sensor_data
        except Exception as e:
            logger.error(f"Error getting sensor data: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get sensor data: {str(e)}")
            return None
    
    def SendActuatorCommand(self, request, context):
        """Принимает команду для актуатора"""
        try:
            self.qsim_service.receive_actuator_command(request)
            logger.debug(f"Processed actuator command via gRPC: {request.actuator_id.value}")
            return Empty()
        except Exception as e:
            logger.error(f"Error processing actuator command: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to process actuator command: {str(e)}")
            return Empty()
    
    def HealthCheck(self, request, context):
        """Проверка состояния сервиса"""
        return HealthResponse(
            status="OK",
            message=f"Q-Sim Service is running normally",
            timestamp=int(time.time())
        )


def serve(config: Dict[str, Any], port: int = 50051):
    """
    Запускает gRPC сервер для Q-Sim Service
    """
    # Инициализируем QSimService
    qsim_service = QSimService(config)
    
    # Создаем gRPC сервер
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = QSimGrpcServicer(qsim_service)
    add_QSimAPIServicer_to_server(servicer, server)
    
    # Привязываем к порту
    listen_addr = f'[::]:{port}'
    server.add_insecure_port(listen_addr)
    
    # Обработчик сигналов для graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Received interrupt signal. Shutting down gRPC server...")
        server.stop(grace=5.0)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запускаем сервер
    server.start()
    logger.info(f"Q-Sim gRPC Server started on {listen_addr}")
    
    try:
        # Запускаем симуляцию в отдельном потоке (опционально)
        # В простом случае можно просто ждать
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Server interrupted")
        server.stop(0)


if __name__ == "__main__":
    import yaml
    
    def load_config(path='config.yaml'):
        config_path = os.path.join(os.path.dirname(__file__), path)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
                
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    # Настройка логирования
    log_config_path = os.path.join(os.path.dirname(__file__), '..', 'q_core_agent', 'core', 'logging.yaml')
    setup_logging(default_path=log_config_path)
    
    # Загружаем конфигурацию и запускаем сервер
    config = load_config()
    grpc_port = config.get('grpc_port', 50051)
    
    logger.info(f"Starting Q-Sim gRPC Server on port {grpc_port}")
    serve(config, grpc_port)