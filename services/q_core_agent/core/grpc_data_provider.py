import grpc
from typing import List

from services.q_core_agent.core.interfaces import IDataProvider
from services.q_core_agent.core.agent_logger import logger

from shared.models.core import BiosStatus, DeviceStatus, FsmStateSnapshot as PydanticFsmStateSnapshot, Proposal, SensorData, ActuatorCommand, DeviceStatusEnum, SensorTypeEnum
from shared.converters.protobuf_pydantic import proto_bios_status_report_to_pydantic_bios_status, pydantic_bios_status_to_proto_bios_status_report, proto_fsm_state_snapshot_to_pydantic_fsm_state_snapshot, pydantic_actuator_command_to_proto_actuator_command, proto_sensor_reading_to_pydantic_sensor_data
from uuid import UUID as PyUUID
from generated.q_sim_api_pb2_grpc import QSimAPIStub
from google.protobuf.empty_pb2 import Empty


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
            self.stub = QSimAPIStub(self.channel)

            # Проверяем соединение
            response = self.stub.HealthCheck(Empty(), timeout=5.0)
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
            ("motor_left", DeviceStatusEnum.OK, "Motor left operational"),
            ("motor_right", DeviceStatusEnum.OK, "Motor right operational"),
            ("lidar_front", DeviceStatusEnum.OK, "LIDAR sensor operational"),
            ("imu_main", DeviceStatusEnum.OK, "IMU sensor operational"),
            (
                "system_controller",
                DeviceStatusEnum.OK,
                "System controller operational",
            ),
        ]

        for device_id, status, message in typical_devices:
            device_status = DeviceStatus(
                device_id=PyUUID(device_id),
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
            snapshot_id=PyUUID("qsim_fsm_001"),
            fsm_instance_id=PyUUID("main_fsm"),
            source_module="qsim_data_provider",
            attempt_count=1,
            ts_wall=datetime.now(UTC),
            context_data={"mode": "legacy", "initialized": "true"},
        )

    def get_proposals(self) -> List[Proposal]:
        """Q-Sim не генерирует предложения, возвращаем пустой список"""
        return []

    def get_sensor_data(self) -> SensorData:
        """Запрашивает данные сенсоров через gRPC"""
        try:
            response = self.stub.GetSensorData(Empty(), timeout=10.0)
            logger.debug(f"Received sensor data via gRPC: {response.sensor_id.value}")
            return proto_sensor_reading_to_pydantic_sensor_data(response)
        except grpc.RpcError as e:
            logger.error(f"Failed to get sensor data via gRPC: {e}")
            # Возвращаем пустое показание при ошибке
            return SensorData(sensor_id=PyUUID("error_sensor"), sensor_type=SensorTypeEnum.OTHER, scalar_data=0.0)

    def send_actuator_command(self, command: ActuatorCommand):
        """Отправляет команду актуатору через gRPC"""
        try:
            proto_command = pydantic_actuator_command_to_proto_actuator_command(command)
            self.stub.SendActuatorCommand(proto_command, timeout=10.0)
            logger.info(f"Sent actuator command via gRPC: {command.actuator_id}")
        except grpc.RpcError as e:
            logger.error(f"Failed to send actuator command via gRPC: {e}")

    def __del__(self):
        """Закрывает gRPC соединение при уничтожении объекта"""
        if self.channel:
            self.channel.close()
