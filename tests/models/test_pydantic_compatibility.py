"""
Тесты совместимости и валидации для Pydantic моделей.

Эти тесты проверяют:
1.  Корректное создание моделей из словарей.
2.  Работу кастомных валидаторов и вычисляемых полей.
3.  Сериализацию в JSON и обратно.
4.  Совместимость между Pydantic-моделями и старыми DTO (где применимо).
"""
import pytest
import json
import uuid

# --- Path setup ---
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

# --- Pydantic Model Imports ---
from shared.models.core import (
    FsmStateSnapshot, FsmStateEnum, FsmTransition,
    BiosStatus, DeviceStatus, DeviceStatusEnum,
    SensorData, SensorTypeEnum,
    Proposal, ProposalSourceEnum, ProposalTypeEnum,
    ActuatorCommand, ActuatorTypeEnum,
    SystemHealth,
    fsm_snapshot_from_dto, fsm_snapshot_to_dto,
    RequestMessage, ResponseMessage, MessageMetadata
)  # noqa: E402

# --- Legacy DTO Imports ---
from services.q_core_agent.state.types import (
    initial_snapshot, TransitionStatus
)  # noqa: E402


class TestFsmCompatibility:
    """Тесты совместимости конечного автомата (FSM)"""

    def test_fsm_state_snapshot_creation(self):
        """Проверка создания снимка состояния FSM"""
        snapshot = FsmStateSnapshot(
            state=FsmStateEnum.IDLE,
            version=1,
            context_data={"reason": "initial state"}
        )
        assert snapshot.state == FsmStateEnum.IDLE
        assert snapshot.version == 1
        assert snapshot.context_data["reason"] == "initial state"

    def test_fsm_transition_creation(self):
        """Проверка создания перехода FSM"""
        transition = FsmTransition(
            from_state=FsmStateEnum.IDLE,
            to_state=FsmStateEnum.ACTIVE,
            trigger_event="User command"
        )
        assert transition.from_state == FsmStateEnum.IDLE
        assert transition.to_state == FsmStateEnum.ACTIVE
        assert transition.trigger_event == "User command"

    def test_dto_to_pydantic_conversion(self):
        """Проверка конвертации из старого DTO в Pydantic модель"""
        legacy_dto = initial_snapshot()
        pydantic_model = fsm_snapshot_from_dto(legacy_dto)
        
        assert pydantic_model.version == legacy_dto.version
        assert pydantic_model.state.name == legacy_dto.state.name
        assert pydantic_model.snapshot_id == uuid.UUID(legacy_dto.snapshot_id)

    def test_pydantic_to_dto_conversion(self):
        """Проверка конвертации из Pydantic модели в старый DTO"""
        pydantic_model = FsmStateSnapshot(
            state=FsmStateEnum.ACTIVE,
            version=5,
            context_data={"source": "test"}
        )
        legacy_dto = fsm_snapshot_to_dto(pydantic_model)
        
        assert legacy_dto.version == pydantic_model.version
        assert legacy_dto.state.name == pydantic_model.state.name
        assert uuid.UUID(legacy_dto.snapshot_id) == pydantic_model.snapshot_id


class TestBiosCompatibility:
    """Тесты совместимости статуса BIOS"""

    def test_bios_status_creation(self):
        """Проверка создания статуса BIOS"""
        devices = [
            DeviceStatus(device_name="cpu", status=DeviceStatusEnum.OK),
            DeviceStatus(device_name="ram", status=DeviceStatusEnum.OK)
        ]
        bios_status = BiosStatus(
            firmware_version="1.0.0",
            health_score=0.99,
            post_results=devices
        )
        assert bios_status.firmware_version == "1.0.0"
        assert len(bios_status.post_results) == 2

    def test_bios_status_all_systems_go(self):
        """Проверка автоматического вычисления all_systems_go"""
        # Все устройства в порядке
        good_devices = [
            DeviceStatus(device_name="device1", status=DeviceStatusEnum.OK),
            DeviceStatus(device_name="device2", status=DeviceStatusEnum.OK)
        ]
        bios_good = BiosStatus(
            firmware_version="1.0",
            health_score=0.95,
            post_results=good_devices,
        )
        
        # Проверяем, что валидатор отработал
        assert bios_good.all_systems_go is True

        # Одно устройство с ошибкой
        bad_devices = [
            DeviceStatus(device_name="device1", status=DeviceStatusEnum.OK),
            DeviceStatus(device_name="device2", status=DeviceStatusEnum.ERROR)
        ]
        bios_bad = BiosStatus(
            firmware_version="1.0",
            health_score=0.5,
            post_results=bad_devices,
        )
        
        # Проверяем, что валидатор отработал
        assert bios_bad.all_systems_go is False


class TestSensorDataCompatibility:
    """Тесты совместимости данных сенсоров"""

    def test_sensor_data_creation(self):
        """Проверка создания данных сенсора"""
        sensor = SensorData(
            sensor_name="temp_sensor",
            sensor_type=SensorTypeEnum.TEMPERATURE,
            scalar_data=23.5
        )
        assert sensor.sensor_name == "temp_sensor"
        assert sensor.sensor_type == SensorTypeEnum.TEMPERATURE
        assert sensor.scalar_data == 23.5

    def test_sensor_data_validation(self):
        """Проверка валидации данных сенсора"""
        # This should pass validation
        SensorData(
            sensor_name="lidar_front",
            sensor_type=SensorTypeEnum.LIDAR,
            vector_data=[1.0, 2.0, 3.0, 4.0]
        )

        # This should fail validation
        with pytest.raises(ValueError):
            SensorData(
                sensor_name="empty_sensor",
                sensor_type=SensorTypeEnum.MOCK
            )

    def test_sensor_json_serialization(self):
        """Проверка сериализации данных сенсора в JSON"""
        sensor = SensorData(
            sensor_name="humidity_sensor",
            sensor_type=SensorTypeEnum.HUMIDITY,
            scalar_data=42.0,
            metadata={"calibrated": True, "range": "0-100"}
        )
        json_data = sensor.model_dump()
        json_str = json.dumps(json_data, default=str)
        loaded_data = json.loads(json_str)
        new_sensor = SensorData(**loaded_data)
        assert new_sensor.sensor_name == sensor.sensor_name
        assert new_sensor.sensor_type == sensor.sensor_type
        assert new_sensor.scalar_data == sensor.scalar_data


class TestProposalCompatibility:
    """Тесты совместимости предложений"""

    def test_proposal_creation(self):
        """Проверка создания предложения"""
        proposal = Proposal(
            proposal_type=ProposalTypeEnum.Q_MIND_REFLEX,
            source=ProposalSourceEnum.RULE_ENGINE,
            confidence=0.85,
            description="Test proposal for navigation adjustment"
        )
        assert proposal.proposal_type == ProposalTypeEnum.Q_MIND_REFLEX
        assert proposal.source == ProposalSourceEnum.RULE_ENGINE
        assert proposal.confidence == 0.85

    def test_proposal_json_serialization(self):
        """Проверка сериализации предложения в JSON"""
        proposal = Proposal(
            proposal_type=ProposalTypeEnum.Q_MIND_PLANNER,
            source=ProposalSourceEnum.NEURAL_ENGINE,
            confidence=0.95,
            description="Complex planning proposal",
            parameters={"target": "destination_alpha", "priority": 5}
        )
        json_data = proposal.model_dump()
        json_str = json.dumps(json_data, default=str)
        loaded_data = json.loads(json_str)
        new_proposal = Proposal(**loaded_data)
        assert new_proposal.proposal_type == proposal.proposal_type
        assert new_proposal.source == proposal.source
        assert new_proposal.confidence == proposal.confidence


class TestActuatorCommandCompatibility:
    """Тесты совместимости команд для исполнительных механизмов"""

    def test_actuator_command_creation(self):
        """Проверка создания команды"""
        command = ActuatorCommand(
            actuator_name="thruster_main",
            actuator_type=ActuatorTypeEnum.THRUSTER,
            command_type="SET_THRUST",
            parameters={"thrust_percent": 75.0, "duration_ms": 5000}
        )
        assert command.actuator_name == "thruster_main"
        assert command.actuator_type == ActuatorTypeEnum.THRUSTER
        assert command.command_type == "SET_THRUST"

    def test_actuator_command_json_serialization(self):
        """Проверка сериализации команды в JSON"""
        command = ActuatorCommand(
            actuator_name="solar_panel_left",
            actuator_type=ActuatorTypeEnum.SOLAR_PANEL,
            command_type="SET_ANGLE",
            parameters={"angle_deg": 45.0, "speed_deg_per_sec": 10.0},
            priority=8
        )
        json_data = command.model_dump()
        json_str = json.dumps(json_data, default=str)
        loaded_data = json.loads(json_str)
        new_command = ActuatorCommand(**loaded_data)
        assert new_command.actuator_name == command.actuator_name
        assert new_command.actuator_type == command.actuator_type
        assert new_command.command_type == command.command_type


class TestSystemHealthCompatibility:
    """Тесты совместимости системного здоровья"""

    def test_system_health_creation(self):
        """Проверка создания данных о системном здоровье и авто-расчета"""
        health = SystemHealth(
            overall_health=0.0, # Это значение будет проигнорировано и пересчитано
            component_health={
                "fsm": 0.95,
                "bios": 0.90,
                "sensors": 0.85,
                "actuators": 0.80
            },
            cpu_usage_percent=45.2,
            memory_usage_percent=67.1,
            fsm_status="IDLE",
            bios_status="ALL_SYSTEMS_GO"
        )
        expected_health = (0.95 + 0.90 + 0.85 + 0.80) / 4
        assert health.overall_health == pytest.approx(expected_health)
        assert health.component_health["fsm"] == 0.95
        assert health.cpu_usage_percent == 45.2
        assert health.memory_usage_percent == 67.1

    def test_system_health_auto_calculation(self):
        """Проверка автоматического расчета общего здоровья"""
        health = SystemHealth(
            overall_health=0.0,  # Должно пересчитаться автоматически
            component_health={
                "component1": 0.8,
                "component2": 0.9,
                "component3": 0.7
            }
        )
        expected_health = (0.8 + 0.9 + 0.7) / 3
        assert health.overall_health == pytest.approx(expected_health)


class TestMessageCompatibility:
    """Тесты совместимости сообщений"""

    def test_request_message_creation(self):
        """Проверка создания запроса"""
        metadata = MessageMetadata(
            source_service="q_core_agent",
            message_type="request"
        )
        request = RequestMessage(
            metadata=metadata,
            payload={"action": "get_fsm_state", "params": {}}
        )
        assert request.metadata.source_service == "q_core_agent"
        assert request.metadata.message_type == "request"
        assert request.payload["action"] == "get_fsm_state"

    def test_response_message_creation(self):
        """Проверка создания ответа"""
        metadata = MessageMetadata(
            source_service="q_sim_service",
            message_type="response"
        )
        response = ResponseMessage(
            metadata=metadata,
            payload={"state": "IDLE", "version": 1},
            success=True
        )
        assert response.metadata.source_service == "q_sim_service"
        assert response.metadata.message_type == "response"
        assert response.success is True
        assert response.payload["state"] == "IDLE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

    BiosStatus, DeviceStatus, DeviceStatusEnum,
    SensorData, SensorTypeEnum,
    Proposal, ProposalSourceEnum, ProposalTypeEnum,
    ActuatorCommand, ActuatorTypeEnum,
    SystemHealth,
    fsm_snapshot_from_dto, fsm_snapshot_to_dto,
    RequestMessage, ResponseMessage, MessageMetadata
)  # noqa: E402

# --- Legacy DTO Imports ---
from services.q_core_agent.state.types import (
    initial_snapshot
)  # noqa: E402


class TestFsmCompatibility:
    """Тесты совместимости конечного автомата (FSM)"""

    def test_fsm_state_snapshot_creation(self):
        """Проверка создания снимка состояния FSM"""
        snapshot = FsmStateSnapshot(
            state=FsmStateEnum.IDLE,
            version=1,
            context_data={"reason": "initial state"}
        )
        assert snapshot.state == FsmStateEnum.IDLE
        assert snapshot.version == 1
        assert snapshot.context_data["reason"] == "initial state"

    def test_fsm_transition_creation(self):
        """Проверка создания перехода FSM"""
        transition = FsmTransition(
            from_state=FsmStateEnum.IDLE,
            to_state=FsmStateEnum.ACTIVE,
            trigger_event="User command"
        )
        assert transition.from_state == FsmStateEnum.IDLE
        assert transition.to_state == FsmStateEnum.ACTIVE
        assert transition.trigger_event == "User command"

    def test_dto_to_pydantic_conversion(self):
        """Проверка конвертации из старого DTO в Pydantic модель"""
        legacy_dto = initial_snapshot()
        pydantic_model = fsm_snapshot_from_dto(legacy_dto)
        
        assert pydantic_model.version == legacy_dto.version
        assert pydantic_model.state.name == legacy_dto.state.name
        assert pydantic_model.snapshot_id == uuid.UUID(legacy_dto.snapshot_id)

    def test_pydantic_to_dto_conversion(self):
        """Проверка конвертации из Pydantic модели в старый DTO"""
        pydantic_model = FsmStateSnapshot(
            state=FsmStateEnum.ACTIVE,
            version=5,
            context_data={"source": "test"}
        )
        legacy_dto = fsm_snapshot_to_dto(pydantic_model)
        
        assert legacy_dto.version == pydantic_model.version
        assert legacy_dto.state.name == pydantic_model.state.name
        assert uuid.UUID(legacy_dto.snapshot_id) == pydantic_model.snapshot_id


class TestBiosCompatibility:
    """Тесты совместимости статуса BIOS"""

    def test_bios_status_creation(self):
        """Проверка создания статуса BIOS"""
        devices = [
            DeviceStatus(device_name="cpu", status=DeviceStatusEnum.OK),
            DeviceStatus(device_name="ram", status=DeviceStatusEnum.OK)
        ]
        bios_status = BiosStatus(
            firmware_version="1.0.0",
            health_score=0.99,
            post_results=devices
        )
        assert bios_status.firmware_version == "1.0.0"
        assert len(bios_status.post_results) == 2

    def test_bios_status_all_systems_go(self):
        """Проверка автоматического вычисления all_systems_go"""
        # Все устройства в порядке
        good_devices = [
            DeviceStatus(device_name="device1", status=DeviceStatusEnum.OK),
            DeviceStatus(device_name="device2", status=DeviceStatusEnum.OK)
        ]
        bios_good = BiosStatus(
            firmware_version="1.0",
            health_score=0.95,
            post_results=good_devices,
        )
        
        # Проверяем, что валидатор отработал
        assert bios_good.all_systems_go is True

        # Одно устройство с ошибкой
        bad_devices = [
            DeviceStatus(device_name="device1", status=DeviceStatusEnum.OK),
            DeviceStatus(device_name="device2", status=DeviceStatusEnum.ERROR)
        ]
        bios_bad = BiosStatus(
            firmware_version="1.0",
            health_score=0.5,
            post_results=bad_devices,
        )
        
        # Проверяем, что валидатор отработал
        assert bios_bad.all_systems_go is False


class TestSensorDataCompatibility:
    """Тесты совместимости данных сенсоров"""

    def test_sensor_data_creation(self):
        """Проверка создания данных сенсора"""
        sensor = SensorData(
            sensor_name="temp_sensor",
            sensor_type=SensorTypeEnum.TEMPERATURE,
            scalar_data=23.5
        )
        assert sensor.sensor_name == "temp_sensor"
        assert sensor.sensor_type == SensorTypeEnum.TEMPERATURE
        assert sensor.scalar_data == 23.5

    def test_sensor_data_validation(self):
        """Проверка валидации данных сенсора"""
        # This should pass validation
        SensorData(
            sensor_name="lidar_front",
            sensor_type=SensorTypeEnum.LIDAR,
            vector_data=[1.0, 2.0, 3.0, 4.0]
        )

        # This should fail validation
        with pytest.raises(ValueError):
            SensorData(
                sensor_name="empty_sensor",
                sensor_type=SensorTypeEnum.MOCK
            )

    def test_sensor_json_serialization(self):
        """Проверка сериализации данных сенсора в JSON"""
        sensor = SensorData(
            sensor_name="humidity_sensor",
            sensor_type=SensorTypeEnum.HUMIDITY,
            scalar_data=42.0,
            metadata={"calibrated": True, "range": "0-100"}
        )
        json_data = sensor.model_dump()
        json_str = json.dumps(json_data, default=str)
        loaded_data = json.loads(json_str)
        new_sensor = SensorData(**loaded_data)
        assert new_sensor.sensor_name == sensor.sensor_name
        assert new_sensor.sensor_type == sensor.sensor_type
        assert new_sensor.scalar_data == sensor.scalar_data


class TestProposalCompatibility:
    """Тесты совместимости предложений"""

    def test_proposal_creation(self):
        """Проверка создания предложения"""
        proposal = Proposal(
            proposal_type=ProposalTypeEnum.Q_MIND_REFLEX,
            source=ProposalSourceEnum.RULE_ENGINE,
            confidence=0.85,
            description="Test proposal for navigation adjustment"
        )
        assert proposal.proposal_type == ProposalTypeEnum.Q_MIND_REFLEX
        assert proposal.source == ProposalSourceEnum.RULE_ENGINE
        assert proposal.confidence == 0.85

    def test_proposal_json_serialization(self):
        """Проверка сериализации предложения в JSON"""
        proposal = Proposal(
            proposal_type=ProposalTypeEnum.Q_MIND_PLANNER,
            source=ProposalSourceEnum.NEURAL_ENGINE,
            confidence=0.95,
            description="Complex planning proposal",
            parameters={"target": "destination_alpha", "priority": 5}
        )
        json_data = proposal.model_dump()
        json_str = json.dumps(json_data, default=str)
        loaded_data = json.loads(json_str)
        new_proposal = Proposal(**loaded_data)
        assert new_proposal.proposal_type == proposal.proposal_type
        assert new_proposal.source == proposal.source
        assert new_proposal.confidence == proposal.confidence


class TestActuatorCommandCompatibility:
    """Тесты совместимости команд для исполнительных механизмов"""

    def test_actuator_command_creation(self):
        """Проверка создания команды"""
        command = ActuatorCommand(
            actuator_name="thruster_main",
            actuator_type=ActuatorTypeEnum.THRUSTER,
            command_type="SET_THRUST",
            parameters={"thrust_percent": 75.0, "duration_ms": 5000}
        )
        assert command.actuator_name == "thruster_main"
        assert command.actuator_type == ActuatorTypeEnum.THRUSTER
        assert command.command_type == "SET_THRUST"

    def test_actuator_command_json_serialization(self):
        """Проверка сериализации команды в JSON"""
        command = ActuatorCommand(
            actuator_name="solar_panel_left",
            actuator_type=ActuatorTypeEnum.SOLAR_PANEL,
            command_type="SET_ANGLE",
            parameters={"angle_deg": 45.0, "speed_deg_per_sec": 10.0},
            priority=8
        )
        json_data = command.model_dump()
        json_str = json.dumps(json_data, default=str)
        loaded_data = json.loads(json_str)
        new_command = ActuatorCommand(**loaded_data)
        assert new_command.actuator_name == command.actuator_name
        assert new_command.actuator_type == command.actuator_type
        assert new_command.command_type == command.command_type


class TestSystemHealthCompatibility:
    """Тесты совместимости системного здоровья"""

    def test_system_health_creation(self):
        """Проверка создания данных о системном здоровье и авто-расчета"""
        health = SystemHealth(
            overall_health=0.0, # Это значение будет проигнорировано и пересчитано
            component_health={
                "fsm": 0.95,
                "bios": 0.90,
                "sensors": 0.85,
                "actuators": 0.80
            },
            cpu_usage_percent=45.2,
            memory_usage_percent=67.1,
            fsm_status="IDLE",
            bios_status="ALL_SYSTEMS_GO"
        )
        expected_health = (0.95 + 0.90 + 0.85 + 0.80) / 4
        assert health.overall_health == pytest.approx(expected_health)
        assert health.component_health["fsm"] == 0.95
        assert health.cpu_usage_percent == 45.2
        assert health.memory_usage_percent == 67.1

    def test_system_health_auto_calculation(self):
        """Проверка автоматического расчета общего здоровья"""
        health = SystemHealth(
            overall_health=0.0,  # Должно пересчитаться автоматически
            component_health={
                "component1": 0.8,
                "component2": 0.9,
                "component3": 0.7
            }
        )
        expected_health = (0.8 + 0.9 + 0.7) / 3
        assert health.overall_health == pytest.approx(expected_health)


class TestMessageCompatibility:
    """Тесты совместимости сообщений"""

    def test_request_message_creation(self):
        """Проверка создания запроса"""
        metadata = MessageMetadata(
            source_service="q_core_agent",
            message_type="request"
        )
        request = RequestMessage(
            metadata=metadata,
            payload={"action": "get_fsm_state", "params": {}}
        )
        assert request.metadata.source_service == "q_core_agent"
        assert request.metadata.message_type == "request"
        assert request.payload["action"] == "get_fsm_state"

    def test_response_message_creation(self):
        """Проверка создания ответа"""
        metadata = MessageMetadata(
            source_service="q_sim_service",
            message_type="response"
        )
        response = ResponseMessage(
            metadata=metadata,
            payload={"state": "IDLE", "version": 1},
            success=True
        )
        assert response.metadata.source_service == "q_sim_service"
        assert response.metadata.message_type == "response"
        assert response.success is True
        assert response.payload["state"] == "IDLE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
