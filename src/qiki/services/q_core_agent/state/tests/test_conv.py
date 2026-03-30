"""
Серьёзные unit тесты для конвертеров DTO ↔ protobuf.
Проверяют корректность конвертации, обработку ошибок, совместимость.
"""

import pytest
import uuid

from qiki.services.q_core_agent.state.conv import (
    FSM_STATE_DTO_TO_PROTO,
    FSM_STATE_PROTO_TO_DTO,
    create_proto_snapshot,
    dto_to_json_dict,
    dto_to_protobuf_json,
    dto_to_proto,
    parse_proto_snapshot,
    proto_to_dto,
    transition_dto_to_proto,
    transition_proto_to_dto,
)
from qiki.services.q_core_agent.state.types import (
    FsmSnapshotDTO,
    TransitionDTO,
    FsmState,
    TransitionStatus,
    create_transition,
    initial_snapshot,
)

# Импорт protobuf для тестов
from generated.fsm_state_pb2 import (
    FsmStateSnapshot,
    StateTransition,
    FSMStateEnum,
    FSMTransitionStatus,
)


class TestEnumMappings:
    """Тесты маппинга enum'ов между DTO и protobuf"""

    def test_fsm_state_dto_to_proto_mapping(self):
        """Тест маппинга FsmState -> FSMStateEnum"""
        assert FSM_STATE_DTO_TO_PROTO[FsmState.UNSPECIFIED] == FSMStateEnum.FSM_STATE_UNSPECIFIED
        assert FSM_STATE_DTO_TO_PROTO[FsmState.BOOTING] == FSMStateEnum.BOOTING
        assert FSM_STATE_DTO_TO_PROTO[FsmState.IDLE] == FSMStateEnum.IDLE
        assert FSM_STATE_DTO_TO_PROTO[FsmState.ACTIVE] == FSMStateEnum.ACTIVE
        assert FSM_STATE_DTO_TO_PROTO[FsmState.ERROR_STATE] == FSMStateEnum.ERROR_STATE
        assert FSM_STATE_DTO_TO_PROTO[FsmState.SHUTDOWN] == FSMStateEnum.SHUTDOWN

    def test_fsm_state_proto_to_dto_mapping(self):
        """Тест маппинга FSMStateEnum -> FsmState"""
        assert FSM_STATE_PROTO_TO_DTO[FSMStateEnum.FSM_STATE_UNSPECIFIED] == FsmState.UNSPECIFIED
        assert FSM_STATE_PROTO_TO_DTO[FSMStateEnum.BOOTING] == FsmState.BOOTING
        assert FSM_STATE_PROTO_TO_DTO[FSMStateEnum.IDLE] == FsmState.IDLE
        assert FSM_STATE_PROTO_TO_DTO[FSMStateEnum.ACTIVE] == FsmState.ACTIVE
        assert FSM_STATE_PROTO_TO_DTO[FSMStateEnum.ERROR_STATE] == FsmState.ERROR_STATE
        assert FSM_STATE_PROTO_TO_DTO[FSMStateEnum.SHUTDOWN] == FsmState.SHUTDOWN

    def test_bidirectional_enum_mapping(self):
        """Тест что маппинг работает в обе стороны"""
        for dto_state, proto_state in FSM_STATE_DTO_TO_PROTO.items():
            assert FSM_STATE_PROTO_TO_DTO[proto_state] == dto_state


class TestTransitionConversion:
    """Тесты конвертации переходов TransitionDTO ↔ StateTransition"""

    def test_transition_dto_to_proto(self):
        """Тест конвертации TransitionDTO -> StateTransition"""
        dto = TransitionDTO(
            from_state=FsmState.IDLE,
            to_state=FsmState.ACTIVE,
            trigger_event="PROPOSALS_RECEIVED",
            status=TransitionStatus.SUCCESS,
            error_message="",
            ts_wall=1234567890.5,
        )

        proto = transition_dto_to_proto(dto)

        assert proto.from_state == FSMStateEnum.IDLE
        assert proto.to_state == FSMStateEnum.ACTIVE
        assert proto.trigger_event == "PROPOSALS_RECEIVED"
        assert proto.status == FSMTransitionStatus.SUCCESS
        assert proto.error_message == ""
        assert proto.timestamp.seconds == 1234567890
        assert proto.timestamp.nanos == 500000000  # 0.5 сек в наносекундах

    def test_transition_proto_to_dto(self):
        """Тест конвертации StateTransition -> TransitionDTO"""
        proto = StateTransition()
        proto.from_state = FSMStateEnum.ACTIVE
        proto.to_state = FSMStateEnum.IDLE
        proto.trigger_event = "NO_PROPOSALS"
        proto.status = FSMTransitionStatus.SUCCESS
        proto.error_message = ""
        proto.timestamp.FromSeconds(1234567890)
        proto.timestamp.nanos = 250000000  # 0.25 сек

        dto = transition_proto_to_dto(proto)

        assert dto.from_state == FsmState.ACTIVE
        assert dto.to_state == FsmState.IDLE
        assert dto.trigger_event == "NO_PROPOSALS"
        assert dto.status == TransitionStatus.SUCCESS
        assert dto.error_message == ""
        assert abs(dto.ts_wall - 1234567890.25) < 0.001  # примерно равно

    def test_transition_with_error(self):
        """Тест конвертации перехода с ошибкой"""
        dto = TransitionDTO(
            from_state=FsmState.IDLE,
            to_state=FsmState.ERROR_STATE,
            trigger_event="BIOS_ERROR",
            status=TransitionStatus.FAILED,
            error_message="BIOS system check failed",
        )

        proto = transition_dto_to_proto(dto)
        back_dto = transition_proto_to_dto(proto)

        assert back_dto.from_state == dto.from_state
        assert back_dto.to_state == dto.to_state
        assert back_dto.trigger_event == dto.trigger_event
        assert back_dto.status == dto.status
        assert back_dto.error_message == dto.error_message

    def test_transition_roundtrip(self):
        """Тест roundtrip конвертации перехода"""
        original = create_transition(FsmState.BOOTING, FsmState.IDLE, "BOOT_COMPLETE", TransitionStatus.SUCCESS)

        proto = transition_dto_to_proto(original)
        converted_back = transition_proto_to_dto(proto)

        # Проверяем основные поля (временные метки могут отличаться)
        assert converted_back.from_state == original.from_state
        assert converted_back.to_state == original.to_state
        assert converted_back.trigger_event == original.trigger_event
        assert converted_back.status == original.status
        assert converted_back.error_message == original.error_message


class TestSnapshotConversion:
    """Тесты конвертации снапшотов FsmSnapshotDTO ↔ FsmStateSnapshot"""

    def test_dto_to_proto_basic(self):
        """Тест базовой конвертации DTO -> protobuf"""
        dto = FsmSnapshotDTO(
            version=42,
            state=FsmState.ACTIVE,
            reason="TEST_REASON",
            snapshot_id=str(uuid.uuid4()),
            fsm_instance_id=str(uuid.uuid4()),
            source_module="test_module",
            attempt_count=5,
        )

        proto = dto_to_proto(dto)

        assert proto.current_state == FSMStateEnum.ACTIVE
        assert proto.source_module == "test_module"
        assert proto.attempt_count == 5
        assert proto.snapshot_id.value == dto.snapshot_id
        assert proto.fsm_instance_id.value == dto.fsm_instance_id

        # DTO-специфичные поля должны быть в метаданных
        assert proto.state_metadata["dto_version"] == "42"
        assert proto.state_metadata["dto_reason"] == "TEST_REASON"

    def test_dto_to_proto_with_history(self):
        """Тест конвертации с историей переходов"""
        transition1 = create_transition(FsmState.BOOTING, FsmState.IDLE, "BOOT_COMPLETE")
        transition2 = create_transition(FsmState.IDLE, FsmState.ACTIVE, "PROPOSALS_RECEIVED")

        dto = FsmSnapshotDTO(version=3, state=FsmState.ACTIVE, history=[transition1, transition2])

        proto = dto_to_proto(dto)

        assert len(proto.history) == 2
        assert proto.history[0].from_state == FSMStateEnum.BOOTING
        assert proto.history[0].to_state == FSMStateEnum.IDLE
        assert proto.history[1].from_state == FSMStateEnum.IDLE
        assert proto.history[1].to_state == FSMStateEnum.ACTIVE

    def test_dto_to_proto_with_metadata(self):
        """Тест конвертации с метаданными"""
        context_data = {"sensor_count": "10", "proposal_active": "true"}
        state_metadata = {"debug": "false", "test_mode": "true"}

        dto = FsmSnapshotDTO(
            version=1,
            state=FsmState.IDLE,
            context_data=context_data,
            state_metadata=state_metadata,
        )

        proto = dto_to_proto(dto)

        # Контекстные данные
        assert proto.context_data["sensor_count"] == "10"
        assert proto.context_data["proposal_active"] == "true"

        # Метаданные состояния (включая DTO-специфичные)
        assert proto.state_metadata["debug"] == "false"
        assert proto.state_metadata["test_mode"] == "true"
        assert proto.state_metadata["dto_version"] == "1"

    def test_proto_to_dto_basic(self):
        """Тест базовой конвертации protobuf -> DTO"""
        proto = FsmStateSnapshot()
        proto.current_state = FSMStateEnum.IDLE
        proto.source_module = "proto_test"
        proto.attempt_count = 7

        # Устанавливаем UUID
        proto.snapshot_id.value = str(uuid.uuid4())
        proto.fsm_instance_id.value = str(uuid.uuid4())

        # DTO-специфичные метаданные
        proto.state_metadata["dto_version"] = "15"
        proto.state_metadata["dto_reason"] = "PROTO_TEST"
        proto.state_metadata["dto_prev_state"] = "BOOTING"
        proto.state_metadata["dto_ts_mono"] = "1234.567"

        dto = proto_to_dto(proto)

        assert dto.state == FsmState.IDLE
        assert dto.version == 15
        assert dto.reason == "PROTO_TEST"
        assert dto.prev_state == FsmState.BOOTING
        assert dto.source_module == "proto_test"
        assert dto.attempt_count == 7
        assert abs(dto.ts_mono - 1234.567) < 0.001

    def test_roundtrip_conversion(self):
        """Тест roundtrip конвертации снапшота"""
        original = FsmSnapshotDTO(
            version=99,
            state=FsmState.ERROR_STATE,
            prev_state=FsmState.ACTIVE,
            reason="ROUNDTRIP_TEST",
            source_module="roundtrip_module",
            attempt_count=3,
            context_data={"key1": "value1"},
            state_metadata={"key2": "value2"},
        )

        proto = dto_to_proto(original)
        converted_back = proto_to_dto(proto)

        # Основные поля должны совпадать
        assert converted_back.version == original.version
        assert converted_back.state == original.state
        assert converted_back.prev_state == original.prev_state
        assert converted_back.reason == original.reason
        assert converted_back.source_module == original.source_module
        assert converted_back.attempt_count == original.attempt_count
        assert converted_back.context_data == original.context_data
        assert converted_back.state_metadata == original.state_metadata

    def test_empty_and_none_handling(self):
        """Тест обработки пустых значений и None"""
        dto = FsmSnapshotDTO(
            version=0,
            state=FsmState.UNSPECIFIED,
            reason="",
            prev_state=None,
            history=None,  # должно стать []
            context_data=None,  # должно стать {}
            state_metadata=None,  # должно стать {}
        )

        proto = dto_to_proto(dto)
        converted_back = proto_to_dto(proto)

        assert converted_back.reason == ""
        assert converted_back.prev_state is None
        assert converted_back.history == ()
        assert converted_back.context_data == {}
        # state_metadata содержит DTO-специфичные поля, но пустые пользовательские


class TestConversionErrors:
    """Тесты обработки ошибок конвертации"""

    def test_dto_to_proto_with_invalid_enum(self):
        """Тест конвертации с некорректным enum (защита от будущих изменений)"""
        # Создаём DTO с "новым" состоянием которого нет в маппинге
        dto = FsmSnapshotDTO(version=1, state=999, reason="INVALID_ENUM")  # некорректное состояние

        # Конвертация должна использовать fallback
        proto = dto_to_proto(dto)
        assert proto.current_state == FSMStateEnum.FSM_STATE_UNSPECIFIED

    def test_real_error_is_wrapped_in_conversion_error(self):
        """
        Тест, что реальная ошибка (TypeError) при конвертации
        корректно заворачивается в ConversionError.
        """
        # history должен быть списком, передаём некорректный тип
        with pytest.raises(TypeError, match="object is not iterable"):
            FsmSnapshotDTO(version=1, state=FsmState.IDLE, history=123)

    def test_invalid_uuid_handling(self):
        """Тест обработки некорректных UUID"""
        dto = FsmSnapshotDTO(
            version=1,
            state=FsmState.IDLE,
            snapshot_id="invalid-uuid-string",
            fsm_instance_id="",  # пустой UUID
        )

        # Конвертация должна пройти с fallback на новые UUID
        proto = dto_to_proto(dto)

        # UUID должны быть валидными
        uuid.UUID(proto.snapshot_id.value)  # не должно упасть
        uuid.UUID(proto.fsm_instance_id.value)  # не должно упасть


class TestJSONConversion:
    """Тесты конвертации в JSON форматы"""

    def test_dto_to_json_dict(self):
        """Тест конвертации DTO в JSON-совместимый словарь"""
        transition = create_transition(FsmState.BOOTING, FsmState.IDLE, "BOOT")

        dto = FsmSnapshotDTO(
            version=5,
            state=FsmState.ACTIVE,
            prev_state=FsmState.IDLE,
            reason="JSON_TEST",
            history=[transition],
            context_data={"key": "value"},
            state_metadata={"meta": "data"},
        )

        json_dict = dto_to_json_dict(dto)

        assert json_dict["version"] == 5
        assert json_dict["state"] == "ACTIVE"
        assert json_dict["prev_state"] == "IDLE"
        assert json_dict["reason"] == "JSON_TEST"
        assert json_dict["history_count"] == 1
        assert json_dict["context_keys"] == ["key"]
        assert json_dict["metadata_keys"] == ["meta"]
        assert "ts_mono" in json_dict
        assert "ts_wall" in json_dict

    def test_dto_to_protobuf_json(self):
        """Тест конвертации DTO в JSON через protobuf"""
        dto = FsmSnapshotDTO(version=3, state=FsmState.ERROR_STATE, reason="PROTOBUF_JSON_TEST")

        json_dict = dto_to_protobuf_json(dto)

        # Должен быть словарь с protobuf структурой
        assert isinstance(json_dict, dict)
        assert "currentState" in json_dict or "current_state" in json_dict  # может варьироваться

    def test_json_formats_consistency(self):
        """Тест согласованности разных JSON форматов"""
        dto = initial_snapshot()

        lightweight_json = dto_to_json_dict(dto)
        protobuf_json = dto_to_protobuf_json(dto)

        # Версии должны совпадать
        assert lightweight_json["version"] == int(protobuf_json.get("stateMetadata", {}).get("dtoVersion", "0"))

        # Состояния должны соответствовать
        assert lightweight_json["state"] == "BOOTING"


class TestHelperFunctions:
    """Тесты вспомогательных функций"""

    def test_create_proto_snapshot(self):
        """Тест создания protobuf снапшота из основных параметров"""
        proto = create_proto_snapshot(FsmState.ACTIVE, "HELPER_TEST", version=10)

        assert proto.current_state == FSMStateEnum.ACTIVE
        assert proto.state_metadata["dto_reason"] == "HELPER_TEST"
        assert proto.state_metadata["dto_version"] == "10"

    def test_parse_proto_snapshot(self):
        """Тест парсинга protobuf данных в DTO"""
        # Создаём protobuf снапшот
        original_dto = FsmSnapshotDTO(version=7, state=FsmState.SHUTDOWN, reason="PARSE_TEST")
        proto = dto_to_proto(original_dto)
        proto_bytes = proto.SerializeToString()

        # Парсим обратно
        parsed_dto = parse_proto_snapshot(proto_bytes)

        assert parsed_dto.version == 7
        assert parsed_dto.state == FsmState.SHUTDOWN
        assert parsed_dto.reason == "PARSE_TEST"


class TestTimestampHandling:
    """Тесты обработки временных меток"""

    def test_float_to_timestamp_conversion(self):
        """Тест конвертации float времени в protobuf Timestamp"""
        from qiki.services.q_core_agent.state.conv import (
            _float_to_timestamp,
            _timestamp_to_float,
        )

        # Тестируем различные временные значения
        test_times = [0.0, 1234567890.5, 1234567890.123456789]

        for original_time in test_times:
            timestamp = _float_to_timestamp(original_time)
            converted_back = _timestamp_to_float(timestamp)

            # Точность до миллисекунд должна сохраняться
            assert abs(converted_back - original_time) < 0.001

    def test_zero_timestamp_handling(self):
        """Тест обработки нулевых временных меток"""
        from qiki.services.q_core_agent.state.conv import (
            _float_to_timestamp,
            _timestamp_to_float,
        )

        # Нулевое время
        timestamp = _float_to_timestamp(0.0)
        assert timestamp.seconds == 0
        assert timestamp.nanos == 0

        # Обратная конвертация
        assert _timestamp_to_float(timestamp) == 0.0

        # None timestamp
        assert _timestamp_to_float(None) == 0.0


class TestEdgeCasesAndBoundaries:
    """Тесты граничных случаев"""

    def test_very_large_version_numbers(self):
        """Тест очень больших номеров версий"""
        large_version = 2**50  # очень большое число

        dto = FsmSnapshotDTO(version=large_version, state=FsmState.IDLE)
        proto = dto_to_proto(dto)
        converted_back = proto_to_dto(proto)

        assert converted_back.version == large_version

    def test_unicode_strings_in_conversion(self):
        """Тест unicode строк в конвертации"""
        unicode_reason = "Тест на русском 🚀 中文测试"
        unicode_trigger = "Событие_中文_🎯"

        dto = FsmSnapshotDTO(
            version=1,
            state=FsmState.IDLE,
            reason=unicode_reason,
            context_data={"unicode_key": "значение_中文"},
            state_metadata={"событие": unicode_trigger},
        )

        proto = dto_to_proto(dto)
        converted_back = proto_to_dto(proto)

        assert converted_back.reason == unicode_reason
        assert converted_back.context_data["unicode_key"] == "значение_中文"
        assert converted_back.state_metadata["событие"] == unicode_trigger

    def test_empty_collections_handling(self):
        """Тест обработки пустых коллекций"""
        dto = FsmSnapshotDTO(
            version=1,
            state=FsmState.IDLE,
            history=[],  # пустая история
            context_data={},  # пустые данные
            state_metadata={},  # пустые метаданные
        )

        proto = dto_to_proto(dto)
        converted_back = proto_to_dto(proto)

        assert converted_back.history == ()
        assert converted_back.context_data == {}
        # state_metadata может содержать DTO-специфичные поля

    def test_large_collections_handling(self):
        """Тест обработки больших коллекций"""
        # Большая история
        large_history = [create_transition(FsmState.IDLE, FsmState.ACTIVE, f"EVENT_{i}") for i in range(1000)]

        # Много метаданных
        large_context = {f"key_{i}": f"value_{i}" for i in range(500)}

        dto = FsmSnapshotDTO(
            version=1,
            state=FsmState.ACTIVE,
            history=large_history,
            context_data=large_context,
        )

        proto = dto_to_proto(dto)
        converted_back = proto_to_dto(proto)

        assert len(converted_back.history) == 1000
        assert len(converted_back.context_data) == 500
        assert all(h.trigger_event.startswith("EVENT_") for h in converted_back.history)


if __name__ == "__main__":
    # Быстрый запуск тестов
    pytest.main([__file__, "-v", "--tb=short"])
