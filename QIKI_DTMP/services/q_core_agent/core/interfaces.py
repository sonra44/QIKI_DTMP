from abc import ABC, abstractmethod
from typing import List, Any

from generated.bios_status_pb2 import BIOSStatus, DeviceStatus
from generated.fsm_state_pb2 import FSMState
from generated.proposal_pb2 import Proposal
from generated.sensor_raw_in_pb2 import SensorReading
from generated.actuator_raw_out_pb2 import ActuatorCommand

class IDataProvider(ABC):
    """
    Abstract interface for providing data to the Q-Core Agent.
    This allows for flexible data sources (mock, real, gRPC, etc.).
    """

    @abstractmethod
    def get_bios_status(self) -> BIOSStatus:
        """Returns the current BIOS status."""
        pass

    @abstractmethod
    def get_fsm_state(self) -> FSMState:
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
        mock_bios_status: BIOSStatus,
        mock_fsm_state: FSMState,
        mock_proposals: List[Proposal],
        mock_sensor_data: SensorReading,
        mock_actuator_response: Any = None
    ):
        self._mock_bios_status = mock_bios_status
        self._mock_fsm_state = mock_fsm_state
        self._mock_proposals = mock_proposals
        self._mock_sensor_data = mock_sensor_data
        self._mock_actuator_response = mock_actuator_response

    def get_bios_status(self) -> BIOSStatus:
        return self._mock_bios_status

    def get_fsm_state(self) -> FSMState:
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

    def get_bios_status(self) -> BIOSStatus:
        # Q-Sim doesn't directly provide BIOS status, so we'll create a dummy one for now
        # In a real scenario, BIOS status would come from a separate source or be part of Q-Sim's state
        return BIOSStatus(all_systems_go=True, firmware_version="sim_v1.0")

    def get_fsm_state(self) -> FSMState:
        # Q-Sim doesn't manage FSM state, so we'll return a dummy initial state
        return FSMState(current_state="BOOTING", phase=FSMState.FSMPhase.BOOTING)

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
    def process_bios_status(self, bios_status: BIOSStatus) -> BIOSStatus:
        """Processes the incoming BIOS status and returns an updated status."""
        pass


class IFSMHandler(ABC):
    """
    Abstract interface for handling FSM state transitions within the Q-Core Agent.
    """

    @abstractmethod
    def process_fsm_state(self, current_fsm_state: FSMState) -> FSMState:
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