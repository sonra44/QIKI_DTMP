import grpc
import time
from typing import List

from services.q_core_agent.core.interfaces import IDataProvider
from services.q_core_agent.core.agent_logger import logger

from generated.bios_status_pb2 import BiosStatusReport, DeviceStatus
from generated.fsm_state_pb2 import FsmStateSnapshot
from generated.proposal_pb2 import Proposal
from generated.sensor_raw_in_pb2 import SensorReading
from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import UUID
from generated.q_sim_api_pb2_grpc import QSimAPIStub
from google.protobuf.empty_pb2 import Empty


class GrpcDataProvider(IDataProvider):
    """
    DataProvider that interacts with Q-Sim Service через gRPC.
    Заменяет прямой доступ к экземпляру QSimService на сетевое взаимодействие.
    """
    
    def __init__(self, grpc_server_address="localhost:50051"):
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
            logger.info(f"Connected to Q-Sim Service at {self.server_address}: {response.message}")
            
        except grpc.RpcError as e:
            logger.error(f"Failed to connect to Q-Sim Service at {self.server_address}: {e}")
            raise ConnectionError(f"Cannot connect to Q-Sim Service: {e}")
    
    def get_bios_status(self) -> BiosStatusReport:
        """
        Возвращает статус BIOS. 
        Q-Sim не управляет BIOS, поэтому генерируем реалистичный мок.
        """
        bios_report = BiosStatusReport(firmware_version="sim_v1.0")
        
        # Симулируем результаты POST для типичных устройств бота
        typical_devices = [
            ("motor_left", DeviceStatus.Status.OK, "Motor left operational"),
            ("motor_right", DeviceStatus.Status.OK, "Motor right operational"), 
            ("lidar_front", DeviceStatus.Status.OK, "LIDAR sensor operational"),
            ("imu_main", DeviceStatus.Status.OK, "IMU sensor operational"),
            ("system_controller", DeviceStatus.Status.OK, "System controller operational")
        ]
        
        for device_id, status, message in typical_devices:
            device_status = DeviceStatus(
                device_id=UUID(value=device_id),
                status=status,
                error_message=message,
                status_code=DeviceStatus.StatusCode.STATUS_CODE_UNSPECIFIED
            )
            bios_report.post_results.append(device_status)
        
        return bios_report

    def get_fsm_state(self) -> FsmStateSnapshot:
        """Q-Sim не управляет FSM состоянием. При StateStore режиме возвращаем пустышку."""
        import os
        if os.environ.get('QIKI_USE_STATESTORE', 'false').lower() == 'true':
            # Возвращаем минимальный протокол для совместимости
            from generated.fsm_state_pb2 import FSMStateEnum
            return FsmStateSnapshot(
                snapshot_id=UUID(value="stub_grpc"),
                current_state=FSMStateEnum.BOOTING,
                fsm_instance_id=UUID(value="stub")
            )
        return FsmStateSnapshot()

    def get_proposals(self) -> List[Proposal]:
        """Q-Sim не генерирует предложения, возвращаем пустой список"""
        return []

    def get_sensor_data(self) -> SensorReading:
        """Запрашивает данные сенсоров через gRPC"""
        try:
            response = self.stub.GetSensorData(Empty(), timeout=10.0)
            logger.debug(f"Received sensor data via gRPC: {response.sensor_id.value}")
            return response
        except grpc.RpcError as e:
            logger.error(f"Failed to get sensor data via gRPC: {e}")
            # Возвращаем пустое показание при ошибке
            return SensorReading(
                sensor_id=UUID(value="error_sensor"),
                scalar_data=0.0
            )

    def send_actuator_command(self, command: ActuatorCommand):
        """Отправляет команду актуатору через gRPC"""
        try:
            self.stub.SendActuatorCommand(command, timeout=10.0)
            logger.info(f"Sent actuator command via gRPC: {command.actuator_id.value}")
        except grpc.RpcError as e:
            logger.error(f"Failed to send actuator command via gRPC: {e}")
    
    def __del__(self):
        """Закрывает gRPC соединение при уничтожении объекта"""
        if self.channel:
            self.channel.close()