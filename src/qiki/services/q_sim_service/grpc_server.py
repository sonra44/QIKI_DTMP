import grpc
import time
import signal
import sys
import os
from concurrent import futures
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(ROOT_DIR)

from services.q_sim_service.logger import setup_logging, logger
from services.q_sim_service.main import QSimService
from generated.q_sim_api_pb2_grpc import QSimAPIServicer, add_QSimAPIServicer_to_server
from generated.q_sim_api_pb2 import HealthResponse
from google.protobuf.empty_pb2 import Empty
from shared.config_models import QSimServiceConfig, load_config


class QSimGrpcServicer(QSimAPIServicer):
    """
    gRPC сервис для взаимодействия с Q-Sim Service.
    """

    def __init__(self, qsim_service: QSimService):
        self.qsim_service = qsim_service
        logger.info("QSimGrpcServicer initialized")

    def GetSensorData(self, request, context):
        """Возвращает данные сенсоров"""
        try:
            sensor_data = self.qsim_service.generate_sensor_data()
            logger.debug(
                f"Returning sensor data via gRPC: {sensor_data.sensor_id.value}"
            )
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
            logger.debug(
                f"Processed actuator command via gRPC: {request.actuator_id.value}"
            )
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
            message="Q-Sim Service is running normally",
            timestamp=int(time.time()),
        )


def serve(config: QSimServiceConfig, port: int = 50051):
    """
    Запускает gRPC сервер для Q-Sim Service
    """
    qsim_service = QSimService(config)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = QSimGrpcServicer(qsim_service)
    add_QSimAPIServicer_to_server(servicer, server)

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    def signal_handler(sig, frame):
        logger.info("Received interrupt signal. Shutting down gRPC server...")
        server.stop(grace=5.0)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    server.start()
    logger.info(f"Q-Sim gRPC Server started on {listen_addr}")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Server interrupted")
        server.stop(0)


if __name__ == "__main__":
    setup_logging(default_path="config.yaml")

    # Путь к конфигу может быть переопределен через переменную окружения
    config_path_str = os.getenv("QIKI_CONFIG_PATH", "services/q_sim_service/config.yaml")
    config_path = Path(config_path_str)

    try:
        config = load_config(config_path, QSimServiceConfig)
        # Порт может быть переопределен в конфиге в будущем
        grpc_port = 50051

        logger.info(f"Starting Q-Sim gRPC Server on port {grpc_port} with config from {config_path.resolve()}")
        serve(config, grpc_port)

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start server due to configuration error: {e}")
        sys.exit(1)