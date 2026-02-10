import os

import grpc
from typing import List

from qiki.services.q_core_agent.core.interfaces import IDataProvider
from qiki.services.q_core_agent.core.agent_logger import logger

from qiki.shared.models.core import BiosStatus, FsmStateSnapshot as PydanticFsmStateSnapshot, Proposal, SensorData, ActuatorCommand, SensorTypeEnum, FsmStateEnum
from qiki.shared.converters.protobuf_pydantic import (
    pydantic_actuator_command_to_proto_actuator_command,
    proto_sensor_reading_to_pydantic_sensor_data,
)
from generated.q_sim_api_pb2_grpc import QSimAPIServiceStub
from generated.q_sim_api_pb2 import (
    GetSensorDataRequest,
    SendActuatorCommandRequest,
    HealthCheckRequest,
)
from qiki.services.q_core_agent.core.bios_http_client import fetch_bios_status


class GrpcSensorDataError(RuntimeError):
    """Base error for gRPC sensor-data retrieval failures."""


class GrpcDataUnavailable(GrpcSensorDataError):
    """gRPC data is unavailable (UNAVAILABLE/internal transport failure)."""


class GrpcTimeout(GrpcDataUnavailable):
    """gRPC data request timed out."""


class GrpcInvalidPayload(GrpcSensorDataError):
    """gRPC response payload is invalid and must not be treated as truth."""


class GrpcDataProvider(IDataProvider):
    """
    DataProvider that interacts with Q-Sim Service через gRPC.
    Заменяет прямой доступ к экземпляру QSimService на сетевое взаимодействие.
    """

    def __init__(self, grpc_server_address="q-sim-service:50051"):
        self.server_address = grpc_server_address
        self.channel = None
        self.stub = None
        self._connect()

    @staticmethod
    def _allow_grpc_fallback() -> bool:
        return os.getenv("QIKI_ALLOW_GRPC_FALLBACK", "false").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _classify_rpc_error(error: grpc.RpcError) -> str:
        try:
            code = error.code()
        except Exception:
            return "unavailable"
        if code == grpc.StatusCode.DEADLINE_EXCEEDED:
            return "timeout"
        if code == grpc.StatusCode.UNAVAILABLE:
            return "unavailable"
        return f"rpc_{str(code).split('.')[-1].lower()}"

    @staticmethod
    def _fallback_sensor_data(*, reason: str, details: str) -> SensorData:
        return SensorData(
            sensor_id="grpc-fallback",
            sensor_type=SensorTypeEnum.OTHER,
            string_data="NO_DATA",
            metadata={
                "is_fallback": True,
                "reason": reason,
                "details": details,
                "source": "grpc_data_provider",
            },
            quality_score=0.0,
        )

    def _connect(self):
        """Устанавливает gRPC соединение с симулятором"""
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = QSimAPIServiceStub(self.channel)

            # Проверяем соединение
            response = self.stub.HealthCheck(HealthCheckRequest(), timeout=5.0)
            logger.info(
                f"Connected to Q-Sim Service at {self.server_address}: {response.message}"
            )

        except grpc.RpcError as e:
            logger.error(
                f"Failed to connect to Q-Sim Service at {self.server_address}: {e}"
            )
            raise ConnectionError(f"Cannot connect to Q-Sim Service: {e}")

    def get_bios_status(self) -> BiosStatus:
        """
        Возвращает статус BIOS.
        No-mocks: BIOS берётся из q-bios-service по HTTP (BIOS_URL).
        """
        return fetch_bios_status()

    def get_fsm_state(self) -> PydanticFsmStateSnapshot:
        """Q-Sim не управляет FSM состоянием. При StateStore режиме возвращаем пустышку."""
        if os.environ.get("QIKI_USE_STATESTORE", "false").lower() == "true":
            # Возвращаем минимальный Pydantic FsmStateSnapshot для совместимости
            return PydanticFsmStateSnapshot(
                current_state=FsmStateEnum.BOOTING,
                previous_state=FsmStateEnum.OFFLINE,
            )
        return PydanticFsmStateSnapshot(
            current_state=FsmStateEnum.BOOTING,
            previous_state=FsmStateEnum.OFFLINE,
            context_data={"mode": "grpc", "initialized": "true"},
        )

    def get_proposals(self) -> List[Proposal]:
        """Q-Sim не генерирует предложения, возвращаем пустой список"""
        return []

    def get_sensor_data(self) -> SensorData:
        """Запрашивает данные сенсоров через gRPC"""
        try:
            response = self.stub.GetSensorData(GetSensorDataRequest(), timeout=10.0)
        except grpc.RpcError as e:
            reason = self._classify_rpc_error(e)
            details = str(e)
            if self._allow_grpc_fallback():
                logger.warning(
                    "gRPC sensor read failed (%s), returning explicit fallback payload: %s",
                    reason,
                    details,
                )
                return self._fallback_sensor_data(reason=reason, details=details)
            if reason == "timeout":
                logger.error("gRPC sensor read timeout; fail-fast without fallback: %s", details)
                raise GrpcTimeout(f"gRPC sensor timeout: {details}") from e
            logger.error("gRPC sensor data unavailable; fail-fast without fallback: %s", details)
            raise GrpcDataUnavailable(f"gRPC sensor unavailable ({reason}): {details}") from e

        reading = response.reading
        sensor_id = getattr(getattr(reading, "sensor_id", None), "value", "")
        if not sensor_id:
            details = "missing sensor_id in GetSensorData response"
            if self._allow_grpc_fallback():
                logger.warning("Invalid gRPC sensor payload, returning explicit fallback payload: %s", details)
                return self._fallback_sensor_data(reason="invalid_payload", details=details)
            logger.error("Invalid gRPC sensor payload; fail-fast without fallback: %s", details)
            raise GrpcInvalidPayload(details)

        try:
            sensor_data = proto_sensor_reading_to_pydantic_sensor_data(reading)
        except Exception as exc:
            details = str(exc)
            if self._allow_grpc_fallback():
                logger.warning(
                    "gRPC sensor payload conversion failed, returning explicit fallback payload: %s",
                    details,
                )
                return self._fallback_sensor_data(reason="invalid_payload", details=details)
            logger.error("gRPC sensor payload conversion failed; fail-fast without fallback: %s", details)
            raise GrpcInvalidPayload(f"invalid gRPC sensor payload: {details}") from exc

        logger.debug("Received sensor data via gRPC: %s", sensor_id)
        return sensor_data

    def send_actuator_command(self, command: ActuatorCommand):
        """Отправляет команду актуатору через gRPC"""
        try:
            proto_command = pydantic_actuator_command_to_proto_actuator_command(command)
            response = self.stub.SendActuatorCommand(
                SendActuatorCommandRequest(command=proto_command),
                timeout=10.0,
            )
            if response.accepted:
                logger.info(f"Sent actuator command via gRPC: {command.actuator_id}")
            else:
                logger.warning(
                    "Actuator command rejected via gRPC: %s (%s)",
                    command.actuator_id,
                    response.message,
                )
        except grpc.RpcError as e:
            logger.error(f"Failed to send actuator command via gRPC: {e}")

    def __del__(self):
        """Закрывает gRPC соединение при уничтожении объекта"""
        if self.channel:
            self.channel.close()
