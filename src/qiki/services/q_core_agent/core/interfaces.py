from abc import ABC, abstractmethod
from typing import List, Any

from qiki.shared.models.core import BiosStatus, FsmStateSnapshot as PydanticFsmStateSnapshot, Proposal, SensorData, ActuatorCommand, DeviceStatus, DeviceStatusEnum
from qiki.services.q_core_agent.core.bios_http_client import fetch_bios_status


class IDataProvider(ABC):
    """
    Abstract interface for providing data to the Q-Core Agent.
    This allows for flexible data sources (mock, real, gRPC, etc.).
    """

    @abstractmethod
    def get_bios_status(self) -> BiosStatus:
        """Returns the current BIOS status."""
        pass

    @abstractmethod
    def get_fsm_state(self) -> PydanticFsmStateSnapshot:
        """Returns the current FSM state."""
        pass

    @abstractmethod
    def get_proposals(self) -> List[Proposal]:
        """Returns a list of proposals from the Q-Mind."""
        pass

    @abstractmethod
    def get_sensor_data(self) -> SensorData:
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
        mock_bios_status: BiosStatus,
        mock_fsm_state: PydanticFsmStateSnapshot,
        mock_proposals: List[Proposal],
        mock_sensor_data: SensorData,
        mock_actuator_response: Any = None,
    ):
        self._mock_bios_status = mock_bios_status
        self._mock_fsm_state = mock_fsm_state
        self._mock_proposals = mock_proposals
        self._mock_sensor_data = mock_sensor_data
        self._mock_actuator_response = mock_actuator_response

    def get_bios_status(self) -> BiosStatus:
        return self._mock_bios_status

    def get_fsm_state(self) -> PydanticFsmStateSnapshot:
        # При StateStore режиме возвращаем пустышку - FSM читается из StateStore
        import os

        if os.environ.get("QIKI_USE_STATESTORE", "false").lower() == "true":
            # Возвращаем минимальный Pydantic FsmStateSnapshot для совместимости
            from qiki.shared.models.core import FsmStateEnum

            return PydanticFsmStateSnapshot(
                current_state=FsmStateEnum.BOOTING,
                previous_state=FsmStateEnum.OFFLINE,
            )
        return self._mock_fsm_state

    def get_proposals(self) -> List[Proposal]:
        return self._mock_proposals

    def get_sensor_data(self) -> SensorData:
        return self._mock_sensor_data

    def send_actuator_command(self, command: ActuatorCommand):
        print(f"MockDataProvider: Sending actuator command {command.actuator_id}")
        return self._mock_actuator_response


class QSimDataProvider(IDataProvider):
    """
    DataProvider that interacts with the Q-Sim Service.
    For MVP, this will directly call methods of a QSimService instance.
    """

    def __init__(self, qsim_service_instance):
        self.qsim_service = qsim_service_instance

    def get_bios_status(self) -> BiosStatus:
        # No-mocks: BIOS comes from q-bios-service (BIOS_URL).
        return fetch_bios_status()

    def get_fsm_state(self) -> PydanticFsmStateSnapshot:
        # При StateStore режиме возвращаем пустышку - FSM читается из StateStore
        import os

        if os.environ.get("QIKI_USE_STATESTORE", "false").lower() == "true":
            # Возвращаем минимальный Pydantic FsmStateSnapshot для совместимости
            from qiki.shared.models.core import FsmStateEnum

            return PydanticFsmStateSnapshot(
                current_state=FsmStateEnum.BOOTING,
                previous_state=FsmStateEnum.OFFLINE,
            )

        # Q-Sim doesn't manage FSM state, so we'll return proper initial BOOTING state
        from qiki.shared.models.core import FsmStateEnum
        from uuid import uuid4
        import time

        fsm_state = PydanticFsmStateSnapshot(
            current_state=FsmStateEnum.BOOTING,  # Начинаем с BOOTING как в Mock режиме
            previous_state=FsmStateEnum.OFFLINE,
            context_data={"mode": "legacy", "initialized": "true"},
            snapshot_id=str(uuid4()),
            fsm_instance_id=str(uuid4()),
            source_module="qsim_data_provider",
            attempt_count=1,
            ts_wall=time.time(),
        )

        return fsm_state

    def get_proposals(self) -> List[Proposal]:
        # Q-Sim doesn't generate proposals, so return empty list
        return []

    def get_sensor_data(self) -> SensorData:
        return self.qsim_service.generate_sensor_data()

    def send_actuator_command(self, command: ActuatorCommand):
        from qiki.shared.converters.protobuf_pydantic import pydantic_actuator_command_to_proto_actuator_command
        proto_command = pydantic_actuator_command_to_proto_actuator_command(command)
        self.qsim_service.receive_actuator_command(proto_command)


class IBiosHandler(ABC):
    """
    Abstract interface for handling BIOS status within the Q-Core Agent.
    """

    @abstractmethod
    def process_bios_status(self, bios_status: BiosStatus) -> BiosStatus:
        """Processes the incoming BIOS status and returns an updated status."""
        pass


class IFSMHandler(ABC):
    """
    Abstract interface for handling FSM state transitions within the Q-Core Agent.
    """

    @abstractmethod
    async def process_fsm_dto(
        self, current_fsm_state: PydanticFsmStateSnapshot
    ) -> PydanticFsmStateSnapshot:
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
