import asyncio
from concurrent import futures
import logging
import os
from pathlib import Path
import sys

import grpc

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(ROOT_DIR)

from qiki.shared.config_models import QSimServiceConfig, load_config
from qiki.services.q_sim_service.main import QSimService
from generated.q_sim_api_pb2_grpc import QSimAPIServiceServicer, add_QSimAPIServiceServicer_to_server
from generated.q_sim_api_pb2 import HealthCheckRequest, HealthCheckResponse, GetSensorDataRequest, GetSensorDataResponse


class QSimAPIService(QSimAPIServiceServicer):
    def __init__(self, sim_service: QSimService):
        self.sim_service = sim_service

    async def HealthCheck(self, request: HealthCheckRequest, context: grpc.aio.ServicerContext) -> HealthCheckResponse:
        return HealthCheckResponse(status="SERVING")

    async def GetSensorData(self, request: GetSensorDataRequest, context: grpc.aio.ServicerContext) -> GetSensorDataResponse:
        sensor_data = await self.sim_service.get_sensor_data()
        return GetSensorDataResponse(reading=sensor_data)


async def serve() -> None:
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    
    config_path = Path(__file__).resolve().parent / "config.yaml"
    config = load_config(config_path, QSimServiceConfig)
    sim_service = QSimService(config)
    
    add_QSimAPIServiceServicer_to_server(QSimAPIService(sim_service), server)
    server.add_insecure_port("[::]:50051")
    await server.start()
    logging.info("gRPC server started on port 50051")
    
    _cleanup_coroutines = []
    async def server_graceful_shutdown():
        logging.info("Starting graceful shutdown...")
        await server.stop(5)

    _cleanup_coroutines.append(server_graceful_shutdown())
    await server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(serve())
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received, shutting down...")
    finally:
        tasks = [t for t in asyncio.all_tasks(loop=loop) if t is not asyncio.current_task(loop=loop)]
        for task in tasks:
            task.cancel()
        group = asyncio.gather(*tasks, return_exceptions=True)
        loop.run_until_complete(group)
        loop.close()
