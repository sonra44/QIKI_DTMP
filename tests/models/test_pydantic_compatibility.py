import pytest
from datetime import datetime, timezone
from google.protobuf.timestamp_pb2 import Timestamp
import uuid # Added import for uuid module

from services.q_core_agent.state.types import FsmSnapshotDTO, TransitionDTO, FsmState, TransitionStatus
from services.q_core_agent.state.conv import dto_to_proto, proto_to_dto, transition_dto_to_proto, transition_proto_to_dto

from generated.fsm_state_pb2 import FsmStateSnapshot, StateTransition, FSMStateEnum, FSMTransitionStatus
from generated.common_types_pb2 import UUID


class TestPydanticProtobufCompatibility:
    """Тесты совместимости между Pydantic DTO и Protobuf сообщениями"""

    def test_fsm_state_enum_conversion(self):
        """Тест конвертации FsmState (Pydantic) <-> FSMStateEnum (Protobuf)"""
        assert dto_to_proto(FsmSnapshotDTO(version=1, state=FsmState.IDLE)).current_state == FSMStateEnum.IDLE
        assert proto_to_dto(FsmStateSnapshot(current_state=FSMStateEnum.ACTIVE)).state == FsmState.ACTIVE

    def test_transition_dto_to_proto_roundtrip(self):
        """Тест roundtrip конвертации TransitionDTO <-> StateTransition"""
        original_dto = TransitionDTO(
            from_state=FsmState.IDLE,
            to_state=FsmState.ACTIVE,
            trigger_event="PROPOSAL_RECEIVED",
            status=TransitionStatus.SUCCESS,
            error_message="",
            ts_wall=datetime.now(timezone.utc).timestamp()
        )

        proto_message = transition_dto_to_proto(original_dto)
        converted_dto = transition_proto_to_dto(proto_message)

        assert converted_dto.from_state == original_dto.from_state
        assert converted_dto.to_state == original_dto.to_state
        assert converted_dto.trigger_event == original_dto.trigger_event
        assert converted_dto.status == original_dto.status
        assert converted_dto.error_message == original_dto.error_message
        # Проверка времени с допуском из-за float точности
        assert abs(converted_dto.ts_wall - original_dto.ts_wall) < 0.001

    def test_fsm_snapshot_dto_to_proto_roundtrip(self):
        """Тест roundtrip конвертации FsmSnapshotDTO <-> FsmStateSnapshot"""
        original_dto = FsmSnapshotDTO(
            version=10,
            state=FsmState.ACTIVE,
            reason="Test reason",
            snapshot_id=str(uuid.uuid4()), # Fixed UUID generation
            fsm_instance_id=str(uuid.uuid4()), # Fixed UUID generation
            source_module="test_module",
            attempt_count=5,
            history=(
                TransitionDTO(from_state=FsmState.BOOTING, to_state=FsmState.IDLE, trigger_event="BOOT"),
                TransitionDTO(from_state=FsmState.IDLE, to_state=FsmState.ACTIVE, trigger_event="ACTIVATE"),
            ),
            context_data={"key1": "value1", "key2": "value2"},
            state_metadata={"meta1": "data1", "meta2": "data2"},
        )

        proto_message = dto_to_proto(original_dto)
        converted_dto = proto_to_dto(proto_message)

        assert converted_dto.version == original_dto.version
        assert converted_dto.state == original_dto.state
        assert converted_dto.reason == original_dto.reason
        assert converted_dto.snapshot_id == original_dto.snapshot_id
        assert converted_dto.fsm_instance_id == original_dto.fsm_instance_id
        assert converted_dto.source_module == original_dto.source_module
        assert converted_dto.attempt_count == original_dto.attempt_count

        # Проверка истории
        assert len(converted_dto.history) == len(original_dto.history)
        assert converted_dto.history[0].trigger_event == original_dto.history[0].trigger_event
        assert converted_dto.history[1].trigger_event == original_dto.history[1].trigger_event

        # Проверка контекстных данных и метаданных
        assert converted_dto.context_data == original_dto.context_data
        assert converted_dto.state_metadata == original_dto.state_metadata

        # Проверка времени с допуском
        assert abs(converted_dto.ts_wall - original_dto.ts_wall) < 0.001

    def test_fsm_snapshot_dto_empty_fields(self):
        """Тест конвертации FsmSnapshotDTO с пустыми/None полями"""
        original_dto = FsmSnapshotDTO(
            version=1,
            state=FsmState.BOOTING,
            reason="",
            history=(),
            context_data={},
            state_metadata={},
        )

        proto_message = dto_to_proto(original_dto)
        converted_dto = proto_to_dto(proto_message)

        assert converted_dto.version == original_dto.version
        assert converted_dto.state == original_dto.state
        assert converted_dto.reason == original_dto.reason
        assert converted_dto.history == original_dto.history
        assert converted_dto.context_data == original_dto.context_data
        assert converted_dto.state_metadata == original_dto.state_metadata

    def test_fsm_snapshot_dto_with_large_history(self):
        """Тест конвертации FsmSnapshotDTO с большой историей"""
        large_history = tuple(
            TransitionDTO(from_state=FsmState.IDLE, to_state=FsmState.ACTIVE, trigger_event=f"Event_{i}")
            for i in range(100)
        )
        original_dto = FsmSnapshotDTO(
            version=100,
            state=FsmState.ACTIVE,
            history=large_history,
        )

        proto_message = dto_to_proto(original_dto)
        converted_dto = proto_to_dto(proto_message)

        assert converted_dto.version == original_dto.version
        assert converted_dto.state == original_dto.state
        assert converted_dto.reason == original_dto.reason
        assert len(converted_dto.history) == len(original_dto.history)
        assert converted_dto.history[-1].trigger_event == original_dto.history[-1].trigger_event
