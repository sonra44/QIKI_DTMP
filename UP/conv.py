"""
Конвертеры между DTO и protobuf для FSM состояний.
Изоляция protobuf логики от внутренней модели данных.
"""

import uuid
from typing import Optional

from google.protobuf.json_format import MessageToDict
from google.protobuf.timestamp_pb2 import Timestamp

from .types import (
    FsmSnapshotDTO,
    TransitionDTO,
    FsmState,
    TransitionStatus,
)

# Импорт protobuf типов (изолированно от core логики)
from generated.fsm_state_pb2 import (
    FsmStateSnapshot,
    StateTransition,
    FSMStateEnum,
    FSMTransitionStatus,
)
from generated.common_types_pb2 import UUID


class ConversionError(Exception):
    """Ошибка при конвертации между DTO и protobuf"""

    pass


# Маппинг enum'ов между DTO и protobuf
FSM_STATE_DTO_TO_PROTO = {
    FsmState.UNSPECIFIED: FSMStateEnum.FSM_STATE_UNSPECIFIED,
    FsmState.BOOTING: FSMStateEnum.BOOTING,
    FsmState.IDLE: FSMStateEnum.IDLE,
    FsmState.ACTIVE: FSMStateEnum.ACTIVE,
    FsmState.ERROR_STATE: FSMStateEnum.ERROR_STATE,
    FsmState.SHUTDOWN: FSMStateEnum.SHUTDOWN,
}

FSM_STATE_PROTO_TO_DTO = {v: k for k, v in FSM_STATE_DTO_TO_PROTO.items()}

TRANSITION_STATUS_DTO_TO_PROTO = {
    TransitionStatus.UNSPECIFIED: FSMTransitionStatus.FSM_TRANSITION_STATUS_UNSPECIFIED,
    TransitionStatus.SUCCESS: FSMTransitionStatus.SUCCESS,
    TransitionStatus.FAILED: FSMTransitionStatus.FAILED,
    TransitionStatus.PENDING: FSMTransitionStatus.PENDING,
}

TRANSITION_STATUS_PROTO_TO_DTO = {
    v: k for k, v in TRANSITION_STATUS_DTO_TO_PROTO.items()
}


def _create_uuid_proto(uuid_str: str) -> UUID:
    """Создать protobuf UUID из строки"""
    uuid_proto = UUID()
    try:
        uuid_obj = uuid.UUID(uuid_str)
        uuid_proto.value = str(uuid_obj)
    except (ValueError, AttributeError):
        # Генерируем новый UUID если строка невалидна
        uuid_proto.value = str(uuid.uuid4())
    return uuid_proto


def _extract_uuid_string(uuid_proto: Optional[UUID]) -> str:
    """Извлечь строку UUID из protobuf"""
    if uuid_proto and uuid_proto.value:
        return uuid_proto.value
    return str(uuid.uuid4())  # fallback


def _timestamp_to_float(ts: Optional[Timestamp]) -> float:
    """Конвертировать protobuf Timestamp в float секунд"""
    if ts is None:
        return 0.0
    return ts.seconds + ts.nanos / 1e9


def _float_to_timestamp(ts_float: float) -> Timestamp:
    """Конвертировать float секунд в protobuf Timestamp"""
    ts = Timestamp()
    if ts_float > 0:
        ts.FromSeconds(int(ts_float))
        # Добавляем наносекунды
        nanos = int((ts_float - int(ts_float)) * 1e9)
        ts.nanos = nanos
    return ts


def transition_dto_to_proto(dto: TransitionDTO) -> StateTransition:
    """Конвертировать TransitionDTO в protobuf StateTransition"""
    try:
        proto = StateTransition()

        # Конвертируем enum'ы
        proto.from_state = FSM_STATE_DTO_TO_PROTO.get(
            dto.from_state, FSMStateEnum.FSM_STATE_UNSPECIFIED
        )
        proto.to_state = FSM_STATE_DTO_TO_PROTO.get(
            dto.to_state, FSMStateEnum.FSM_STATE_UNSPECIFIED
        )
        proto.status = TRANSITION_STATUS_DTO_TO_PROTO.get(
            dto.status, FSMTransitionStatus.FSM_TRANSITION_STATUS_UNSPECIFIED
        )

        # Строковые поля
        proto.trigger_event = dto.trigger_event
        proto.error_message = dto.error_message

        # Временная метка (используем wall time)
        if dto.ts_wall > 0:
            proto.timestamp.CopyFrom(_float_to_timestamp(dto.ts_wall))

        return proto

    except Exception as e:
        raise ConversionError(f"Ошибка конвертации TransitionDTO->proto: {e}")


def transition_proto_to_dto(proto: StateTransition) -> TransitionDTO:
    """Конвертировать protobuf StateTransition в TransitionDTO"""
    try:
        return TransitionDTO(
            from_state=FSM_STATE_PROTO_TO_DTO.get(
                proto.from_state, FsmState.UNSPECIFIED
            ),
            to_state=FSM_STATE_PROTO_TO_DTO.get(proto.to_state, FsmState.UNSPECIFIED),
            trigger_event=proto.trigger_event or "",
            status=TRANSITION_STATUS_PROTO_TO_DTO.get(
                proto.status, TransitionStatus.UNSPECIFIED
            ),
            error_message=proto.error_message or "",
            ts_wall=_timestamp_to_float(proto.timestamp),
            ts_mono=0.0,  # не храним в protobuf, только wall time
        )
    except Exception as e:
        raise ConversionError(f"Ошибка конвертации StateTransition->DTO: {e}")


def dto_to_proto(dto: FsmSnapshotDTO) -> FsmStateSnapshot:
    """
    Конвертировать FsmSnapshotDTO в protobuf FsmStateSnapshot.
    Главная функция для экспорта состояния в внешние интерфейсы.
    """
    try:
        proto = FsmStateSnapshot()

        # UUID'ы
        if dto.snapshot_id:
            proto.snapshot_id.CopyFrom(_create_uuid_proto(dto.snapshot_id))
        if dto.fsm_instance_id:
            proto.fsm_instance_id.CopyFrom(_create_uuid_proto(dto.fsm_instance_id))

        # Временная метка (wall time)
        if dto.ts_wall > 0:
            proto.timestamp.CopyFrom(_float_to_timestamp(dto.ts_wall))

        # Основное состояние
        proto.current_state = FSM_STATE_DTO_TO_PROTO.get(
            dto.state, FSMStateEnum.FSM_STATE_UNSPECIFIED
        )

        # Строковые поля
        proto.source_module = dto.source_module or ""
        proto.attempt_count = dto.attempt_count

        # История переходов
        if dto.history:
            for transition_dto in dto.history:
                transition_proto = transition_dto_to_proto(transition_dto)
                proto.history.append(transition_proto)

        # Контекстные данные
        if dto.context_data:
            for key, value in dto.context_data.items():
                proto.context_data[key] = str(value)

        # Метаданные состояния
        if dto.state_metadata:
            for key, value in dto.state_metadata.items():
                proto.state_metadata[key] = str(value)

        # Добавляем DTO-специфичные метаданные в state_metadata
        proto.state_metadata["dto_version"] = str(dto.version)
        proto.state_metadata["dto_reason"] = dto.reason
        if dto.prev_state:
            proto.state_metadata["dto_prev_state"] = dto.prev_state.name
        proto.state_metadata["dto_ts_mono"] = str(dto.ts_mono)

        return proto

    except Exception as e:
        raise ConversionError(f"Ошибка конвертации FsmSnapshotDTO->proto: {e}")


def proto_to_dto(proto: FsmStateSnapshot) -> FsmSnapshotDTO:
    """
    Конвертировать protobuf FsmStateSnapshot в FsmSnapshotDTO.
    Используется редко - в основном для тестов или импорта внешних состояний.
    """
    try:
        # Извлекаем UUID'ы
        snapshot_id = _extract_uuid_string(proto.snapshot_id)
        fsm_instance_id = _extract_uuid_string(proto.fsm_instance_id)

        # Временные метки
        ts_wall = _timestamp_to_float(proto.timestamp)

        # Основное состояние
        current_state = FSM_STATE_PROTO_TO_DTO.get(
            proto.current_state, FsmState.UNSPECIFIED
        )

        # История переходов
        history = []
        for transition_proto in proto.history:
            transition_dto = transition_proto_to_dto(transition_proto)
            history.append(transition_dto)

        # Контекстные данные и метаданные
        context_data = dict(proto.context_data) if proto.context_data else {}
        state_metadata = dict(proto.state_metadata) if proto.state_metadata else {}

        # Извлекаем DTO-специфичные поля из метаданных
        version = int(state_metadata.pop("dto_version", "0"))
        reason = state_metadata.pop("dto_reason", "")
        prev_state_name = state_metadata.pop("dto_prev_state", None)
        prev_state = None
        if prev_state_name:
            try:
                prev_state = FsmState[prev_state_name]
            except KeyError:
                pass
        ts_mono = float(state_metadata.pop("dto_ts_mono", "0.0"))

        return FsmSnapshotDTO(
            version=version,
            state=current_state,
            prev_state=prev_state,
            reason=reason,
            ts_mono=ts_mono,
            ts_wall=ts_wall,
            snapshot_id=snapshot_id,
            fsm_instance_id=fsm_instance_id,
            source_module=proto.source_module or "unknown",
            attempt_count=proto.attempt_count,
            history=history,
            context_data=context_data,
            state_metadata=state_metadata,
        )

    except Exception as e:
        raise ConversionError(f"Ошибка конвертации FsmStateSnapshot->DTO: {e}")


def dto_to_json_dict(dto: FsmSnapshotDTO) -> dict:
    """
    Конвертировать DTO в JSON-совместимый словарь для логирования.
    Более лёгкая альтернатива полной protobuf конвертации.
    """
    return {
        "version": dto.version,
        "state": dto.state.name,
        "prev_state": dto.prev_state.name if dto.prev_state else None,
        "reason": dto.reason,
        "ts_mono": dto.ts_mono,
        "ts_wall": dto.ts_wall,
        "snapshot_id": dto.snapshot_id,
        "fsm_instance_id": dto.fsm_instance_id,
        "source_module": dto.source_module,
        "attempt_count": dto.attempt_count,
        "history_count": len(dto.history) if dto.history else 0,
        "context_keys": list(dto.context_data.keys()) if dto.context_data else [],
        "metadata_keys": list(dto.state_metadata.keys()) if dto.state_metadata else [],
    }


def dto_to_protobuf_json(dto: FsmSnapshotDTO) -> dict:
    """
    Конвертировать DTO в JSON через protobuf (для совместимости с существующими логами).
    Более медленная, но полностью совместимая с текущим форматом логов.
    """
    proto = dto_to_proto(dto)
    try:
        return MessageToDict(proto)
    except Exception as e:
        # Оборачиваем любые ошибки конвертации в единый тип
        raise ConversionError(f"Ошибка protobuf->JSON: {e}")


# Удобные функции для быстрого использования
def create_proto_snapshot(
    state: FsmState, reason: str, version: int = 1
) -> FsmStateSnapshot:
    """Создать protobuf снапшот из основных параметров"""
    dto = FsmSnapshotDTO(version=version, state=state, reason=reason)
    return dto_to_proto(dto)


def parse_proto_snapshot(proto_data: bytes) -> FsmSnapshotDTO:
    """Распарсить protobuf данные в DTO"""
    proto = FsmStateSnapshot()
    proto.ParseFromString(proto_data)
    return proto_to_dto(proto)
