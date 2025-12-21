import grpc
from typing import List

from qiki.services.q_core_agent.core.interfaces import IDataProvider
from qiki.services.q_core_agent.core.agent_logger import logger

from datetime import datetime, UTC
from qiki.shared.models.core import BiosStatus, DeviceStatus, FsmStateSnapshot as PydanticFsmStateSnapshot, Proposal, SensorData, ActuatorCommand, DeviceStatusEnum, SensorTypeEnum, FsmStateEnum
from qiki.shared.converters.protobuf_pydantic import (
    pydantic_actuator_command_to_proto_actuator_command,
    proto_sensor_reading_to_pydantic_sensor_data,
)
from uuid import uuid4
from generated.q_sim_api_pb2_grpc import QSimAPIServiceStub
from generated.q_sim_api_pb2 import (
    GetSensorDataRequest,
    SendActuatorCommandRequest,
    HealthCheckRequest,
)


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
        Q-Sim не управляет BIOS, поэтому генерируем реалистичный мок.
        """
        bios_report = BiosStatus(
            bios_version="sim_v1.0",
            firmware_version="sim_v1.0",
            post_results=[],
            timestamp=datetime.now(UTC),
        )

        # Симулируем результаты POST для типичных устройств бота
        typical_devices = [
            ("motor_left", "Left Motor", DeviceStatusEnum.OK, "Motor left operational"),
            ("motor_right", "Right Motor", DeviceStatusEnum.OK, "Motor right operational"),
            ("system_controller", "System Controller", DeviceStatusEnum.OK, "System controller operational"),
            ("lidar_front", "Front LIDAR", DeviceStatusEnum.OK, "LIDAR sensor operational"),
            ("imu_main", "Main IMU", DeviceStatusEnum.OK, "IMU sensor operational"),
            ("sensor_imu", "IMU Sensor", DeviceStatusEnum.OK, "IMU sensor operational"),
            ("sensor_thermal", "Thermal Sensors", DeviceStatusEnum.OK, "Thermal sensors operational"),
            ("sensor_radiation", "Radiation Sensors", DeviceStatusEnum.OK, "Radiation sensors operational"),
            ("sensor_docking", "Docking Sensors", DeviceStatusEnum.OK, "Docking sensors operational"),
            ("sensor_proximity", "Proximity Sensors", DeviceStatusEnum.OK, "Proximity sensors operational"),
            ("sensor_solar", "Solar Sensor", DeviceStatusEnum.OK, "Solar sensor operational"),
            ("sensor_star_tracker", "Star Tracker", DeviceStatusEnum.OK, "Star tracker operational"),
            ("radar_360", "Radar 360", DeviceStatusEnum.OK, "Radar operational"),
            ("lidar", "Lidar", DeviceStatusEnum.OK, "Lidar operational"),
            ("spectrometer", "Spectrometer", DeviceStatusEnum.OK, "Spectrometer operational"),
            ("magnetometer", "Magnetometer", DeviceStatusEnum.OK, "Magnetometer operational"),
        ]

        for device_id, device_name, status, message in typical_devices:
            device_status = DeviceStatus(
                device_id=device_id,
                device_name=device_name,
                status=status,
                status_message=message,
            )
            bios_report.post_results.append(device_status)

        return bios_report

    def get_fsm_state(self) -> PydanticFsmStateSnapshot:
        """Q-Sim не управляет FSM состоянием. При StateStore режиме возвращаем пустышку."""
        import os

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
            reading = response.reading
            logger.debug(f"Received sensor data via gRPC: {reading.sensor_id.value}")
            return proto_sensor_reading_to_pydantic_sensor_data(reading)
        except grpc.RpcError as e:
            logger.error(f"Failed to get sensor data via gRPC: {e}")
            # Возвращаем пустое показание при ошибке
            return SensorData(sensor_id=str(uuid4()), sensor_type=SensorTypeEnum.OTHER, scalar_data=0.0)

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
