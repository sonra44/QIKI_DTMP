from __future__ import annotations

import asyncio
import logging
from concurrent import futures
from pathlib import Path

import grpc

from generated.q_sim_api_pb2 import (
    GetSensorDataRequest,
    GetSensorDataResponse,
    HealthCheckRequest,
    HealthCheckResponse,
)
from generated.q_sim_api_pb2_grpc import (
    QSimAPIServiceServicer,
    add_QSimAPIServiceServicer_to_server,
)
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig, load_config


class QSimAPIService(QSimAPIServiceServicer):
    def __init__(self, sim_service: QSimService):
        self.sim_service = sim_service

    async def HealthCheck(
        self, request: HealthCheckRequest, context: grpc.aio.ServicerContext
    ) -> HealthCheckResponse:
        return HealthCheckResponse(status="SERVING")

    async def GetSensorData(
        self, request: GetSensorDataRequest, context: grpc.aio.ServicerContext
    ) -> GetSensorDataResponse:
        sensor_data = await self.sim_service.get_sensor_data()
        return GetSensorDataResponse(reading=sensor_data)


async def sim_service_loop(sim_service: QSimService) -> None:
    """Background task that runs the simulation step loop."""
    logging.info("Starting QSimService background loop")
    try:
        while True:
            sim_service.step()
            await asyncio.sleep(sim_service.config.sim_tick_interval)
    except asyncio.CancelledError:
        logging.info("QSimService loop cancelled")
        raise


async def serve() -> None:
    """Start gRPC server with background simulation loop."""
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))

    config_path = Path(__file__).resolve().parent / "config.yaml"
    config = load_config(config_path, QSimServiceConfig)
    sim_service = QSimService(config)

    add_QSimAPIServiceServicer_to_server(QSimAPIService(sim_service), server)
    server.add_insecure_port("[::]:50051")
    await server.start()
    logging.info("gRPC server started on port 50051")

    sim_task = asyncio.create_task(sim_service_loop(sim_service))

    async def server_graceful_shutdown() -> None:
        logging.info("Starting graceful shutdown...")
        sim_task.cancel()
        try:
            await sim_task
        except asyncio.CancelledError:
            pass
        await server.stop(5)

    try:
        await server.wait_for_termination()
    finally:
        await server_graceful_shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())

