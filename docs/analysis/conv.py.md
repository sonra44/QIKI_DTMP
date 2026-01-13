# Анализ файла conv.py

## Вход и цель
- **Файл**: conv.py
- **Итог**: Обзор конвертеров между DTO и protobuf для FSM состояний

## Сбор контекста
- **Исходник**: /home/sonra44/QIKI_DTMP/services/q_core_agent/state/conv.py
- **Связанные файлы**:
  - services/q_core_agent/state/types.py (DTO типы FSM)
  - services/q_core_agent/state/store.py (хранилище состояний)
  - services/q_core_agent/state/tests/test_conv.py (тесты конвертеров)
  - generated/fsm_state_pb2.py (protobuf типы FSM)
  - generated/common_types_pb2.py (общие protobuf типы)

**[Факт]**: Файл реализует конвертеры между внутренними DTO типами и protobuf сообщениями для FSM состояний.

## Локализация артефакта
- **Точный путь**: /home/sonra44/QIKI_DTMP/services/q_core_agent/state/conv.py
- **Окружение**: Python 3.x, google.protobuf, uuid, typing

## Фактический разбор
### Ключевые классы и функции:
- **ConversionError**: Исключение для ошибок конвертации
- **Маппинги enum'ов**: FSM_STATE_DTO_TO_PROTO, FSM_STATE_PROTO_TO_DTO, TRANSITION_STATUS_DTO_TO_PROTO, TRANSITION_STATUS_PROTO_TO_DTO
- **Вспомогательные функции**:
  - `_create_uuid_proto()`: Создание protobuf UUID из строки
  - `_extract_uuid_string()`: Извлечение строки UUID из protobuf
  - `_timestamp_to_float()`: Конвертация protobuf Timestamp в float
  - `_float_to_timestamp()`: Конвертация float в protobuf Timestamp
- **Основные конвертеры**:
  - `transition_dto_to_proto()`: TransitionDTO → StateTransition
  - `transition_proto_to_dto()`: StateTransition → TransitionDTO
  - `dto_to_proto()`: FsmSnapshotDTO → FsmStateSnapshot
  - `proto_to_dto()`: FsmStateSnapshot → FsmSnapshotDTO
- **Функции для логирования**:
  - `dto_to_json_dict()`: DTO → JSON-совместимый словарь
  - `dto_to_protobuf_json()`: DTO → JSON через protobuf
- **Удобные функции**:
  - `create_proto_snapshot()`: Создание protobuf снапшота
  - `parse_proto_snapshot()`: Парсинг protobuf данных

**[Факт]**: Конвертеры обеспечивают изоляцию внутренней модели данных от внешних protobuf интерфейсов.

## Роль в системе и связи
- **Как участвует в потоке**: Обеспечивает преобразование данных между внутренним представлением и внешними интерфейсами
- **Кто вызывает**: StateStore, FSMHandler, логирование, внешние сервисы
- **Что от него ждут**: Корректное и надежное преобразование данных без потерь
- **Чем он рискует**: Ошибки конвертации могут привести к сбоям в работе системы

**[Факт]**: Конвертеры являются критически важным компонентом для обеспечения совместимости между внутренней архитектурой и внешними интерфейсами.

## Несоответствия и риски
1. **Средний риск**: При ошибках конвертации выбрасываются общие ConversionError без детальной информации
2. **Средний риск**: Нет явной проверки целостности данных при конвертации
3. **Низкий риск**: Нет поддержки обратной совместимости с предыдущими версиями форматов
4. **Низкий риск**: Нет явной документации по формату хранения DTO-специфичных данных в метаданных

**[Гипотеза]**: Может потребоваться добавить проверки целостности данных и улучшить обработку ошибок.

## Мини-патчи (safe-fix)
**[Патч]**: Улучшить обработку ошибок с детальной информацией:
```python
def transition_dto_to_proto(dto: TransitionDTO) -> StateTransition:
    """Конвертировать TransitionDTO в protobuf StateTransition"""
    try:
        # Проверка входных данных
        if not isinstance(dto, TransitionDTO):
            raise ConversionError(f"Expected TransitionDTO, got {type(dto)}")
            
        proto = StateTransition()
        
        # Конвертируем enum'ы с проверкой
        from_state = FSM_STATE_DTO_TO_PROTO.get(dto.from_state)
        to_state = FSM_STATE_DTO_TO_PROTO.get(dto.to_state)
        status = TRANSITION_STATUS_DTO_TO_PROTO.get(dto.status)
        
        if from_state is None:
            raise ConversionError(f"Unknown from_state: {dto.from_state}")
        if to_state is None:
            raise ConversionError(f"Unknown to_state: {dto.to_state}")
        if status is None:
            raise ConversionError(f"Unknown status: {dto.status}")
            
        proto.from_state = from_state
        proto.to_state = to_state
        proto.status = status
        
        # Строковые поля
        proto.trigger_event = dto.trigger_event or ""
        proto.error_message = dto.error_message or ""
        
        # Временная метка (используем wall time)
        if dto.ts_wall > 0:
            proto.timestamp.CopyFrom(_float_to_timestamp(dto.ts_wall))
        
        return proto
        
    except ConversionError:
        # Перебрасываем ConversionError как есть
        raise
    except Exception as e:
        raise ConversionError(f"Ошибка конвертации TransitionDTO->proto: {e}") from e
```

## Рефактор-скетч (по желанию)
```python
"""
Конвертеры между DTO и protobuf для FSM состояний.
Изоляция protobuf логики от внутренней модели данных.
"""
import uuid
from typing import Optional, List, Dict, Any
import logging

from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.timestamp_pb2 import Timestamp

from .types import (
    FsmSnapshotDTO, TransitionDTO, FsmState, TransitionStatus,
    initial_snapshot, create_transition, next_snapshot
)

# Импорт protobuf типов (изолированно от core логики)
from generated.fsm_state_pb2 import (
    FsmStateSnapshot, StateTransition, FSMStateEnum, FSMTransitionStatus
)
from generated.common_types_pb2 import UUID

# Настройка логирования
logger = logging.getLogger(__name__)

class ConversionError(Exception):
    """Ошибка при конвертации между DTO и protobuf"""
    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.original_exception = original_exception

class DataIntegrityError(ConversionError):
    """Ошибка целостности данных при конвертации"""
    pass

# Маппинг enum'ов между DTO и protobuf
FSM_STATE_DTO_TO_PROTO: Dict[FsmState, FSMStateEnum] = {
    FsmState.UNSPECIFIED: FSMStateEnum.FSM_STATE_UNSPECIFIED,
    FsmState.BOOTING: FSMStateEnum.BOOTING,
    FsmState.IDLE: FSMStateEnum.IDLE,
    FsmState.ACTIVE: FSMStateEnum.ACTIVE,
    FsmState.ERROR_STATE: FSMStateEnum.ERROR_STATE,
    FsmState.SHUTDOWN: FSMStateEnum.SHUTDOWN,
}

FSM_STATE_PROTO_TO_DTO: Dict[FSMStateEnum, FsmState] = {v: k for k, v in FSM_STATE_DTO_TO_PROTO.items()}

TRANSITION_STATUS_DTO_TO_PROTO: Dict[TransitionStatus, FSMTransitionStatus] = {
    TransitionStatus.UNSPECIFIED: FSMTransitionStatus.FSM_TRANSITION_STATUS_UNSPECIFIED,
    TransitionStatus.SUCCESS: FSMTransitionStatus.SUCCESS,
    TransitionStatus.FAILED: FSMTransitionStatus.FAILED,
    TransitionStatus.PENDING: FSMTransitionStatus.PENDING,
}

TRANSITION_STATUS_PROTO_TO_DTO: Dict[FSMTransitionStatus, TransitionStatus] = {
    v: k for k, v in TRANSITION_STATUS_DTO_TO_PROTO.items()
}

def _validate_uuid_string(uuid_str: str) -> bool:
    """Проверка валидности строки UUID"""
    try:
        uuid.UUID(uuid_str)
        return True
    except (ValueError, AttributeError):
        return False

def _create_uuid_proto(uuid_str: str) -> UUID:
    """Создать protobuf UUID из строки"""
    uuid_proto = UUID()
    try:
        if _validate_uuid_string(uuid_str):
            uuid_proto.value = uuid_str
        else:
            # Генерируем новый UUID если строка невалидна
            logger.warning(f"Invalid UUID string: {uuid_str}, generating new one")
            uuid_proto.value = str(uuid.uuid4())
    except Exception as e:
        logger.error(f"Error creating UUID proto: {e}")
        uuid_proto.value = str(uuid.uuid4())  # fallback
    return uuid_proto

def _extract_uuid_string(uuid_proto: Optional[UUID]) -> str:
    """Извлечь строку UUID из protobuf"""
    if uuid_proto and uuid_proto.value:
        if _validate_uuid_string(uuid_proto.value):
            return uuid_proto.value
        else:
            logger.warning(f"Invalid UUID in proto: {uuid_proto.value}")
    
    # fallback
    new_uuid = str(uuid.uuid4())
    logger.debug(f"Generated fallback UUID: {new_uuid}")
    return new_uuid

def _timestamp_to_float(ts: Optional[Timestamp]) -> float:
    """Конвертировать protobuf Timestamp в float секунд"""
    if ts is None:
        return 0.0
    try:
        return ts.seconds + ts.nanos / 1e9
    except Exception as e:
        logger.error(f"Error converting timestamp to float: {e}")
        return 0.0

def _float_to_timestamp(ts_float: float) -> Timestamp:
    """Конвертировать float секунд в protobuf Timestamp"""
    ts = Timestamp()
    try:
        if ts_float > 0:
            ts.FromSeconds(int(ts_float))
            # Добавляем наносекунды
            nanos = int((ts_float - int(ts_float)) * 1e9)
            ts.nanos = max(0, min(nanos, 999999999))  # ограничиваем диапазон
    except Exception as e:
        logger.error(f"Error converting float to timestamp: {e}")
    return ts

def _validate_transition_dto(dto: TransitionDTO) -> None:
    """Проверка валидности TransitionDTO"""
    if not isinstance(dto, TransitionDTO):
        raise DataIntegrityError(f"Expected TransitionDTO, got {type(dto)}")
    
    # Проверяем enum'ы
    if not isinstance(dto.from_state, FsmState):
        raise DataIntegrityError(f"Invalid from_state type: {type(dto.from_state)}")
    
    if not isinstance(dto.to_state, FsmState):
        raise DataIntegrityError(f"Invalid to_state type: {type(dto.to_state)}")
    
    if not isinstance(dto.status, TransitionStatus):
        raise DataIntegrityError(f"Invalid status type: {type(dto.status)}")

def transition_dto_to_proto(dto: TransitionDTO) -> StateTransition:
    """Конвертировать TransitionDTO в protobuf StateTransition"""
    try:
        # Проверка входных данных
        _validate_transition_dto(dto)
        
        proto = StateTransition()
        
        # Конвертируем enum'ы с проверкой
        from_state = FSM_STATE_DTO_TO_PROTO.get(dto.from_state)
        to_state = FSM_STATE_DTO_TO_PROTO.get(dto.to_state)
        status = TRANSITION_STATUS_DTO_TO_PROTO.get(dto.status)
        
        if from_state is None:
            raise ConversionError(f"Unknown from_state: {dto.from_state}")
        if to_state is None:
            raise ConversionError(f"Unknown to_state: {dto.to_state}")
        if status is None:
            raise ConversionError(f"Unknown status: {dto.status}")
            
        proto.from_state = from_state
        proto.to_state = to_state
        proto.status = status
        
        # Строковые поля
        proto.trigger_event = str(dto.trigger_event) if dto.trigger_event else ""
        proto.error_message = str(dto.error_message) if dto.error_message else ""
        
        # Временная метка (используем wall time)
        if dto.ts_wall > 0:
            proto.timestamp.CopyFrom(_float_to_timestamp(dto.ts_wall))
        
        return proto
        
    except ConversionError:
        # Перебрасываем ConversionError как есть
        raise
    except Exception as e:
        raise ConversionError(f"Ошибка конвертации TransitionDTO->proto: {e}", e) from e

def transition_proto_to_dto(proto: StateTransition) -> TransitionDTO:
    """Конвертировать protobuf StateTransition в TransitionDTO"""
    try:
        # Проверка входных данных
        if not isinstance(proto, StateTransition):
            raise DataIntegrityError(f"Expected StateTransition, got {type(proto)}")
        
        # Конвертируем enum'ы
        from_state = FSM_STATE_PROTO_TO_DTO.get(proto.from_state, FsmState.UNSPECIFIED)
        to_state = FSM_STATE_PROTO_TO_DTO.get(proto.to_state, FsmState.UNSPECIFIED)
        status = TRANSITION_STATUS_PROTO_TO_DTO.get(proto.status, TransitionStatus.UNSPECIFIED)
        
        # Извлекаем строковые поля
        trigger_event = str(proto.trigger_event) if proto.trigger_event else ""
        error_message = str(proto.error_message) if proto.error_message else ""
        
        # Конвертируем временную метку
        ts_wall = _timestamp_to_float(proto.timestamp)
        
        return TransitionDTO(
            from_state=from_state,
            to_state=to_state,
            trigger_event=trigger_event,
            status=status,
            error_message=error_message,
            ts_wall=ts_wall,
            ts_mono=0.0  # не храним в protobuf, только wall time
        )
        
    except Exception as e:
        raise ConversionError(f"Ошибка конвертации StateTransition->DTO: {e}", e) from e

def _validate_snapshot_dto(dto: FsmSnapshotDTO) -> None:
    """Проверка валидности FsmSnapshotDTO"""
    if not isinstance(dto, FsmSnapshotDTO):
        raise DataIntegrityError(f"Expected FsmSnapshotDTO, got {type(dto)}")
    
    # Проверяем основные поля
    if not isinstance(dto.state, FsmState):
        raise DataIntegrityError(f"Invalid state type: {type(dto.state)}")
    
    if not isinstance(dto.version, int):
        raise DataIntegrityError(f"Invalid version type: {type(dto.version)}")

def dto_to_proto(dto: FsmSnapshotDTO) -> FsmStateSnapshot:
    """
    Конвертировать FsmSnapshotDTO в protobuf FsmStateSnapshot.
    Главная функция для экспорта состояния в внешние интерфейсы.
    """
    try:
        # Проверка входных данных
        _validate_snapshot_dto(dto)
        
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
        current_state = FSM_STATE_DTO_TO_PROTO.get(dto.state, FSMStateEnum.FSM_STATE_UNSPECIFIED)
        proto.current_state = current_state
        
        # Строковые поля
        proto.source_module = str(dto.source_module) if dto.source_module else ""
        proto.attempt_count = int(dto.attempt_count) if dto.attempt_count else 0
        
        # История переходов
        if dto.history:
            for transition_dto in dto.history:
                try:
                    transition_proto = transition_dto_to_proto(transition_dto)
                    proto.history.append(transition_proto)
                except Exception as e:
                    logger.warning(f"Skipping invalid transition in history: {e}")
                    continue
                
        # Контекстные данные
        if dto.context_data:
            for key, value in dto.context_data.items():
                try:
                    proto.context_data[str(key)] = str(value)
                except Exception as e:
                    logger.warning(f"Skipping invalid context data item {key}: {e}")
                    continue
                
        # Метаданные состояния
        if dto.state_metadata:
            for key, value in dto.state_metadata.items():
                try:
                    proto.state_metadata[str(key)] = str(value)
                except Exception as e:
                    logger.warning(f"Skipping invalid state metadata item {key}: {e}")
                    continue
                
        # Добавляем DTO-специфичные метаданные в state_metadata
        proto.state_metadata['dto_version'] = str(dto.version)
        proto.state_metadata['dto_reason'] = str(dto.reason) if dto.reason else ""
        if dto.prev_state:
            proto.state_metadata['dto_prev_state'] = str(dto.prev_state.name)
        proto.state_metadata['dto_ts_mono'] = str(dto.ts_mono)
        
        return proto
        
    except Exception as e:
        raise ConversionError(f"Ошибка конвертации FsmSnapshotDTO->proto: {e}", e) from e

def proto_to_dto(proto: FsmStateSnapshot) -> FsmSnapshotDTO:
    """
    Конвертировать protobuf FsmStateSnapshot в FsmSnapshotDTO.
    Используется редко - в основном для тестов или импорта внешних состояний.
    """
    try:
        # Проверка входных данных
        if not isinstance(proto, FsmStateSnapshot):
            raise DataIntegrityError(f"Expected FsmStateSnapshot, got {type(proto)}")
        
        # Извлекаем UUID'ы
        snapshot_id = _extract_uuid_string(proto.snapshot_id)
        fsm_instance_id = _extract_uuid_string(proto.fsm_instance_id)
        
        # Временные метки
        ts_wall = _timestamp_to_float(proto.timestamp)
        
        # Основное состояние
        current_state = FSM_STATE_PROTO_TO_DTO.get(proto.current_state, FsmState.UNSPECIFIED)
        
        # История переходов
        history = []
        for transition_proto in proto.history:
            try:
                transition_dto = transition_proto_to_dto(transition_proto)
                history.append(transition_dto)
            except Exception as e:
                logger.warning(f"Skipping invalid transition in history: {e}")
                continue
            
        # Контекстные данные и метаданные
        context_data = {}
        if proto.context_data:
            for key, value in proto.context_data.items():
                try:
                    context_data[str(key)] = str(value)
                except Exception as e:
                    logger.warning(f"Skipping invalid context data item {key}: {e}")
                    continue
        
        state_metadata = {}
        if proto.state_metadata:
            for key, value in proto.state_metadata.items():
                try:
                    state_metadata[str(key)] = str(value)
                except Exception as e:
                    logger.warning(f"Skipping invalid state metadata item {key}: {e}")
                    continue
        
        # Извлекаем DTO-специфичные поля из метаданных
        version_str = state_metadata.pop('dto_version', '0')
        try:
            version = int(version_str)
        except (ValueError, TypeError):
            logger.warning(f"Invalid version in metadata: {version_str}, using 0")
            version = 0
            
        reason = state_metadata.pop('dto_reason', '')
        
        prev_state_name = state_metadata.pop('dto_prev_state', None)
        prev_state = None
        if prev_state_name:
            try:
                prev_state = FsmState[prev_state_name]
            except KeyError:
                logger.warning(f"Unknown prev_state in metadata: {prev_state_name}")
        
        ts_mono_str = state_metadata.pop('dto_ts_mono', '0.0')
        try:
            ts_mono = float(ts_mono_str)
        except (ValueError, TypeError):
            logger.warning(f"Invalid ts_mono in metadata: {ts_mono_str}, using 0.0")
            ts_mono = 0.0
        
        return FsmSnapshotDTO(
            version=version,
            state=current_state,
            prev_state=prev_state,
            reason=reason,
            ts_mono=ts_mono,
            ts_wall=ts_wall,
            snapshot_id=snapshot_id,
            fsm_instance_id=fsm_instance_id,
            source_module=str(proto.source_module) if proto.source_module else "unknown",
            attempt_count=int(proto.attempt_count) if proto.attempt_count else 0,
            history=history,
            context_data=context_data,
            state_metadata=state_metadata
        )
        
    except Exception as e:
        raise ConversionError(f"Ошибка конвертации FsmStateSnapshot->DTO: {e}", e) from e

def dto_to_json_dict(dto: FsmSnapshotDTO) -> dict:
    """
    Конвертировать DTO в JSON-совместимый словарь для логирования.
    Более лёгкая альтернатива полной protobuf конвертации.
    """
    try:
        if not isinstance(dto, FsmSnapshotDTO):
            raise DataIntegrityError(f"Expected FsmSnapshotDTO, got {type(dto)}")
        
        return {
            'version': int(dto.version),
            'state': str(dto.state.name),
            'prev_state': str(dto.prev_state.name) if dto.prev_state else None,
            'reason': str(dto.reason) if dto.reason else "",
            'ts_mono': float(dto.ts_mono),
            'ts_wall': float(dto.ts_wall),
            'snapshot_id': str(dto.snapshot_id),
            'fsm_instance_id': str(dto.fsm_instance_id),
            'source_module': str(dto.source_module) if dto.source_module else "",
            'attempt_count': int(dto.attempt_count),
            'history_count': len(dto.history) if dto.history else 0,
            'context_keys': [str(k) for k in dto.context_data.keys()] if dto.context_data else [],
            'metadata_keys': [str(k) for k in dto.state_metadata.keys()] if dto.state_metadata else []
        }
    except Exception as e:
        raise ConversionError(f"Ошибка конвертации DTO->JSON dict: {e}", e) from e

def dto_to_protobuf_json(dto: FsmSnapshotDTO) -> dict:
    """
    Конвертировать DTO в JSON через protobuf (для совместимости с существующими логами).
    Более медленная, но полностью совместимая с текущим форматом логов.
    """
    try:
        proto = dto_to_proto(dto)
        return MessageToDict(proto)
    except Exception as e:
        raise ConversionError(f"Ошибка конвертации DTO->Protobuf JSON: {e}", e) from e

# Удобные функции для быстрого использования
def create_proto_snapshot(state: FsmState, reason: str, version: int = 1) -> FsmStateSnapshot:
    """Создать protobuf снапшот из основных параметров"""
    try:
        dto = FsmSnapshotDTO(version=int(version), state=state, reason=str(reason))
        return dto_to_proto(dto)
    except Exception as e:
        raise ConversionError(f"Ошибка создания protobuf снапшота: {e}", e) from e

def parse_proto_snapshot(proto_data: bytes) -> FsmSnapshotDTO:
    """Распарсить protobuf данные в DTO"""
    try:
        if not isinstance(proto_data, bytes):
            raise DataIntegrityError(f"Expected bytes, got {type(proto_data)}")
        
        proto = FsmStateSnapshot()
        proto.ParseFromString(proto_data)
        return proto_to_dto(proto)
    except Exception as e:
        raise ConversionError(f"Ошибка парсинга protobuf данных: {e}", e) from e

# Функции для проверки совместимости
def check_dto_proto_compatibility(dto: FsmSnapshotDTO) -> bool:
    """Проверка совместимости DTO с protobuf форматом"""
    try:
        proto = dto_to_proto(dto)
        back_dto = proto_to_dto(proto)
        return True
    except Exception:
        return False

def get_conversion_stats() -> Dict[str, Any]:
    """Получение статистики конвертации"""
    return {
        'dto_to_proto_mapping': len(FSM_STATE_DTO_TO_PROTO),
        'proto_to_dto_mapping': len(FSM_STATE_PROTO_TO_DTO),
        'status_mapping': len(TRANSITION_STATUS_DTO_TO_PROTO)
    }