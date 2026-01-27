from __future__ import annotations

import asyncio
import json
import logging
import os
from concurrent import futures
from pathlib import Path

import grpc
import nats

from generated.q_sim_api_pb2 import (
    GetSensorDataRequest,
    GetSensorDataResponse,
    HealthCheckRequest,
    HealthCheckResponse,
    SendActuatorCommandRequest,
    SendActuatorCommandResponse,
    GetRadarFrameRequest,
    GetRadarFrameResponse,
)
from qiki.shared.converters.radar_proto_pydantic import model_frame_to_proto
from generated.q_sim_api_pb2_grpc import (
    QSimAPIServiceServicer,
    add_QSimAPIServiceServicer_to_server,
)
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig, load_config
from qiki.shared.models.core import CommandMessage
from qiki.shared.nats_subjects import COMMANDS_CONTROL


class QSimAPIService(QSimAPIServiceServicer):
    def __init__(self, sim_service: QSimService):
        self.sim_service = sim_service

    async def HealthCheck(self, request: HealthCheckRequest, context: grpc.aio.ServicerContext) -> HealthCheckResponse:
        return HealthCheckResponse(status="SERVING")

    async def GetSensorData(
        self, request: GetSensorDataRequest, context: grpc.aio.ServicerContext
    ) -> GetSensorDataResponse:
        sensor_data = await self.sim_service.get_sensor_data()
        return GetSensorDataResponse(reading=sensor_data)

    async def SendActuatorCommand(
        self, request: SendActuatorCommandRequest, context: grpc.aio.ServicerContext
    ) -> SendActuatorCommandResponse:
        try:
            self.sim_service.receive_actuator_command(request.command)
            return SendActuatorCommandResponse(accepted=True, message="ok")
        except Exception as exc:
            return SendActuatorCommandResponse(accepted=False, message=str(exc))

    async def GetRadarFrame(
        self, request: GetRadarFrameRequest, context: grpc.aio.ServicerContext
    ) -> GetRadarFrameResponse:
        try:
            frame = self.sim_service.generate_radar_frame()
            proto_frame = model_frame_to_proto(frame)
            return GetRadarFrameResponse(frame=proto_frame)
        except Exception as exc:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return GetRadarFrameResponse()


async def sim_service_loop(sim_service: QSimService) -> None:
    """Background task that runs the simulation step loop."""
    logging.info("Starting QSimService background loop")
    try:
        while True:
            sim_service.tick()
            await asyncio.sleep(sim_service.config.sim_tick_interval)
    except asyncio.CancelledError:
        logging.info("QSimService loop cancelled")
        raise


async def control_commands_loop(sim_service: QSimService) -> None:
    """NATS consumer for operator control commands (no mocks)."""
    enabled = os.getenv("CONTROL_NATS_ENABLED", "1").strip().lower()
    if enabled in ("0", "false", ""):
        logging.info("CONTROL_NATS_ENABLED disabled; skipping COMMANDS_CONTROL consumer.")
        return

    nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
    try:
        nc = await nats.connect(nats_url)
    except Exception as exc:
        logging.warning("Failed to connect to NATS %s for control commands: %s", nats_url, exc)
        return

    logging.info("Subscribed to %s (control) on %s", COMMANDS_CONTROL, nats_url)

    async def handler(msg) -> None:
        try:
            payload = json.loads(msg.data.decode("utf-8"))
            cmd = CommandMessage.model_validate(payload)
        except Exception as exc:
            logging.warning("Invalid control command payload: %s", exc)
            return

        try:
            handled = sim_service.apply_control_command(cmd)
            if handled:
                logging.info("Applied control command: %s", cmd.command_name)
        except Exception as exc:
            logging.warning("Failed applying control command %s: %s", cmd.command_name, exc)

    stop = asyncio.Event()
    sub = await nc.subscribe(COMMANDS_CONTROL, cb=handler)
    try:
        await stop.wait()
    except asyncio.CancelledError:
        raise
    finally:
        try:
            await sub.unsubscribe()
        except Exception:
            pass
        try:
            await nc.close()
        except Exception:
            pass


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
    control_task = asyncio.create_task(control_commands_loop(sim_service))

    async def server_graceful_shutdown() -> None:
        logging.info("Starting graceful shutdown...")
        sim_task.cancel()
        control_task.cancel()
        try:
            await sim_task
        except asyncio.CancelledError:
            pass
        try:
            await control_task
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
