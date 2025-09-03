from abc import ABC, abstractmethod
from typing import List, Any

from generated.bios_status_pb2 import BiosStatusReport, DeviceStatus
from generated.fsm_state_pb2 import FsmStateSnapshot, StateTransition
from generated.proposal_pb2 import Proposal
from generated.sensor_raw_in_pb2 import SensorReading
from generated.actuator_raw_out_pb2 import ActuatorCommand

class IDataProvider(ABC):
    """
    Abstract interface for providing data to the Q-Core Agent.
    This allows for flexible data sources (mock, real, gRPC, etc.).
    """

    @abstractmethod
    def get_bios_status(self) -> BiosStatusReport:
        """Returns the current BIOS status."""
        pass

    @abstractmethod
    def get_fsm_state(self) -> FsmStateSnapshot:
        """Returns the current FSM state."""
        pass

    @abstractmethod
    def get_proposals(self) -> List[Proposal]:
        """Returns a list of proposals from the Q-Mind."""
        pass

    @abstractmethod
    def get_sensor_data(self) -> SensorReading:
        """Returns the latest sensor data."""
        pass

    @abstractmethod
    def send_actuator_command(self, command: ActuatorCommand):
        """Sends an actuator command to the environment."""
        pass

class MockDataProvider(IDataProvider):
    """
    Mock implementation of IDataProvider for testing and development.
    Provides dummy data for BIOS status, FSM state, and proposals.
    """
    def __init__(
        self,
        mock_bios_status: BiosStatusReport,
        mock_fsm_state: FsmStateSnapshot,
        mock_proposals: List[Proposal],
        mock_sensor_data: SensorReading,
        mock_actuator_response: Any = None
    ):
        self._mock_bios_status = mock_bios_status
        self._mock_fsm_state = mock_fsm_state
        self._mock_proposals = mock_proposals
        self._mock_sensor_data = mock_sensor_data
        self._mock_actuator_response = mock_actuator_response

    def get_bios_status(self) -> BiosStatusReport:
        return self._mock_bios_status

    def get_fsm_state(self) -> FsmStateSnapshot:
        # При StateStore режиме возвращаем пустышку - FSM читается из StateStore
        import os
        if os.environ.get('QIKI_USE_STATESTORE', 'false').lower() == 'true':
            # Возвращаем минимальный протокол для совместимости
            from generated.fsm_state_pb2 import FSMStateEnum
            from generated.common_types_pb2 import UUID
            return FsmStateSnapshot(
                snapshot_id=UUID(value="stub_fsm"),
                current_state=FSMStateEnum.BOOTING,
                fsm_instance_id=UUID(value="stub")
            )
        return self._mock_fsm_state

    def get_proposals(self) -> List[Proposal]:
        return self._mock_proposals

    def get_sensor_data(self) -> SensorReading:
        return self._mock_sensor_data

    def send_actuator_command(self, command: ActuatorCommand):
        print(f"MockDataProvider: Sending actuator command {command.actuator_id.value}")
        return self._mock_actuator_response


class QSimDataProvider(IDataProvider):
    """
    DataProvider that interacts with the Q-Sim Service.
    For MVP, this will directly call methods of a QSimService instance.
    """
    def __init__(self, qsim_service_instance):
        self.qsim_service = qsim_service_instance

    def get_bios_status(self) -> BiosStatusReport:
        # Generate realistic BIOS status with POST test results for known devices
        # This simulates what a real BIOS would report after Power-On Self-Test
        bios_report = BiosStatusReport(firmware_version="sim_v1.0")
        
        # Simulate POST results for typical bot devices
        from generated.common_types_pb2 import UUID
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
        
        # BIOS will determine all_systems_go based on device statuses
        # Leave it unset here - BiosHandler will process it properly
        return bios_report

    def get_fsm_state(self) -> FsmStateSnapshot:
        # При StateStore режиме возвращаем пустышку - FSM читается из StateStore
        import os
        if os.environ.get('QIKI_USE_STATESTORE', 'false').lower() == 'true':
            # Возвращаем минимальный протокол для совместимости
            from generated.fsm_state_pb2 import FSMStateEnum
            from generated.common_types_pb2 import UUID
            return FsmStateSnapshot(
                snapshot_id=UUID(value="stub_fsm"),
                current_state=FSMStateEnum.BOOTING,
                fsm_instance_id=UUID(value="stub")
            )
            
        # Q-Sim doesn't manage FSM state, so we'll return proper initial BOOTING state
        from generated.fsm_state_pb2 import FSMStateEnum
        from generated.common_types_pb2 import UUID
        from google.protobuf.timestamp_pb2 import Timestamp
        
        fsm_state = FsmStateSnapshot(
            snapshot_id=UUID(value="qsim_fsm_001"),
            current_state=FSMStateEnum.BOOTING,  # Начинаем с BOOTING как в Mock режиме
            fsm_instance_id=UUID(value="main_fsm"),
            source_module="qsim_data_provider",
            attempt_count=1
        )
        
        # Добавляем timestamp
        timestamp = Timestamp()
        timestamp.GetCurrentTime()
        fsm_state.timestamp.CopyFrom(timestamp)
        
        # Добавляем context_data
        fsm_state.context_data["mode"] = "legacy"
        fsm_state.context_data["initialized"] = "true"
        
        return fsm_state

    def get_proposals(self) -> List[Proposal]:
        # Q-Sim doesn't generate proposals, so return empty list
        return []

    def get_sensor_data(self) -> SensorReading:
        return self.qsim_service.generate_sensor_data()

    def send_actuator_command(self, command: ActuatorCommand):
        self.qsim_service.receive_actuator_command(command)


class IBiosHandler(ABC):
    """
    Abstract interface for handling BIOS status within the Q-Core Agent.
    """

    @abstractmethod
    def process_bios_status(self, bios_status: BiosStatusReport) -> BiosStatusReport:
        """Processes the incoming BIOS status and returns an updated status."""
        pass


class IFSMHandler(ABC):
    """
    Abstract interface for handling FSM state transitions within the Q-Core Agent.
    """

    @abstractmethod
    def process_fsm_state(self, current_fsm_state: FsmStateSnapshot) -> FsmStateSnapshot:
        """Processes the current FSM state and returns the next FSM state."""
        pass


class IProposalEvaluator(ABC):
    """
    Abstract interface for evaluating and selecting proposals from the Q-Mind.
    """

    @abstractmethod
    def evaluate_proposals(self, proposals: List[Proposal]) -> List[Proposal]:
        """Evaluates a list of proposals and returns a filtered/prioritized list of accepted proposals."""
        pass


class IRuleEngine(ABC):
    """
    Abstract interface for the Rule Engine, responsible for generating proposals based on predefined rules.
    """

    @abstractmethod
    def generate_proposals(self, context: Any) -> List[Proposal]:
        """Generates a list of proposals based on the current agent context."""
        pass


class INeuralEngine(ABC):
    """
    Abstract interface for the Neural Engine, responsible for generating proposals based on ML models.
    """

    @abstractmethod
    def generate_proposals(self, context: Any) -> List[Proposal]:
        """Generates a list of proposals based on the current agent context using ML models."""
        pass