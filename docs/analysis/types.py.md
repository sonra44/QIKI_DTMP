# Анализ файла types.py

## Вход и цель
- **Файл**: types.py
- **Итог**: Обзор DTO модели для FSM состояний

## Сбор контекста
- **Исходник**: /home/sonra44/QIKI_DTMP/services/q_core_agent/state/types.py
- **Связанные файлы**:
  - services/q_core_agent/state/store.py (хранилище состояний)
  - services/q_core_agent/state/conv.py (конвертеры)
  - services/q_core_agent/state/tests/test_types.py (тесты типов)
  - services/q_core_agent/core/fsm_handler.py (обработчик FSM)

**[Факт]**: Файл реализует DTO модель для FSM состояний без зависимостей от protobuf, используя иммутабельные dataclass'ы.

## Локализация артефакта
- **Точный путь**: /home/sonra44/QIKI_DTMP/services/q_core_agent/state/types.py
- **Окружение**: Python 3.x, dataclasses, enum, typing

## Фактический разбор
### Ключевые классы и функции:
- **FsmState**: Enum для FSM состояний
  - UNSPECIFIED = 0
  - BOOTING = 1
  - IDLE = 2
  - ACTIVE = 3
  - ERROR_STATE = 4
  - SHUTDOWN = 5
- **TransitionStatus**: Enum для статуса перехода FSM
  - UNSPECIFIED = 0
  - SUCCESS = 1
  - FAILED = 2
  - PENDING = 3
- **TransitionDTO**: DTO для перехода состояния FSM (immutable dataclass)
  - from_state: FsmState (исходное состояние)
  - to_state: FsmState (целевое состояние)
  - trigger_event: str (событие-триггер)
  - status: TransitionStatus (статус перехода)
  - error_message: str (сообщение об ошибке)
  - ts_mono: float (monotonic time)
  - ts_wall: float (wall clock time)
- **FsmSnapshotDTO**: DTO для снапшота FSM состояния (immutable dataclass)
  - version: int (версия состояния)
  - state: FsmState (текущее состояние)
  - reason: str (причина перехода)
  - ts_mono: float (monotonic time)
  - ts_wall: float (wall clock time)
  - snapshot_id: str (UUID снапшота)
  - prev_state: Optional[FsmState] (предыдущее состояние)
  - fsm_instance_id: str (UUID инстанса FSM)
  - source_module: str (модуль-источник)
  - attempt_count: int (количество попыток)
  - history: List[TransitionDTO] (история переходов)
  - context_data: Dict[str, str] (контекстные данные)
  - state_metadata: Dict[str, str] (метаданные состояния)
- **Вспомогательные функции**:
  - `initial_snapshot()`: Создание начального снапшота для COLD_START
  - `create_transition()`: Хелпер для создания перехода состояния
  - `next_snapshot()`: Создание нового снапшота на базе текущего

**[Факт]**: Все DTO являются иммутабельными благодаря frozen=True в dataclass декораторах.

## Роль в системе и связи
- **Как участвует в потоке**: Предоставляет внутреннюю модель данных для FSM состояний без внешних зависимостей
- **Кто вызывает**: StateStore, FSMHandler, конвертеры, тесты
- **Что от него ждут**: Безопасные, иммутабельные структуры данных для работы с состояниями FSM
- **Чем он рискует**: Изменения в структуре DTO могут повлиять на всю систему состояний

**[Факт]**: DTO модели обеспечивают изоляцию внутренней логики от внешних зависимостей.

## Несоответствия и риски
1. **Средний риск**: Все строковые поля в словарях имеют тип str, что может быть ограничением для сложных данных
2. **Средний риск**: Нет явной валидации входных данных в конструкторах DTO
3. **Низкий риск**: Нет поддержки сериализации/десериализации в стандартные форматы (JSON, pickle)
4. **Низкий риск**: Нет явной документации по семантике каждого поля

**[Гипотеза]**: Может потребоваться добавить валидацию данных и поддержку сериализации.

## Мини-патчи (safe-fix)
**[Патч]**: Добавить валидацию входных данных:
```python
@dataclass(frozen=True)
class TransitionDTO:
    """DTO для перехода состояния FSM (immutable)"""
    from_state: FsmState
    to_state: FsmState
    trigger_event: str
    status: TransitionStatus = TransitionStatus.SUCCESS
    error_message: str = ""
    ts_mono: float = 0.0
    ts_wall: float = 0.0
    
    def __post_init__(self):
        # Валидация входных данных
        if not isinstance(self.from_state, FsmState):
            raise TypeError(f"from_state must be FsmState, got {type(self.from_state)}")
        if not isinstance(self.to_state, FsmState):
            raise TypeError(f"to_state must be FsmState, got {type(self.to_state)}")
        if not isinstance(self.trigger_event, str):
            raise TypeError(f"trigger_event must be str, got {type(self.trigger_event)}")
        if not isinstance(self.status, TransitionStatus):
            raise TypeError(f"status must be TransitionStatus, got {type(self.status)}")
        if not isinstance(self.error_message, str):
            raise TypeError(f"error_message must be str, got {type(self.error_message)}")
        if not isinstance(self.ts_mono, (int, float)):
            raise TypeError(f"ts_mono must be number, got {type(self.ts_mono)}")
        if not isinstance(self.ts_wall, (int, float)):
            raise TypeError(f"ts_wall must be number, got {type(self.ts_wall)}")
            
        # Устанавливаем временные метки если не заданы
        if self.ts_mono == 0.0:
            object.__setattr__(self, 'ts_mono', time.monotonic())
        if self.ts_wall == 0.0:
            object.__setattr__(self, 'ts_wall', time.time())
```

## Рефактор-скетч (по желанию)
```python
"""
DTO модель для FSM состояний без зависимостей от protobuf.
Immutable dataclasses для безопасной работы с состоянием.
"""
from dataclasses import dataclass, asdict
from enum import IntEnum
from typing import Optional, List, Dict, Any, Union
import time
import uuid
import json
import logging

logger = logging.getLogger(__name__)

class FsmState(IntEnum):
    """FSM состояния (копия из protobuf enum без привязки к proto)"""
    UNSPECIFIED = 0
    BOOTING = 1
    IDLE = 2
    ACTIVE = 3
    ERROR_STATE = 4
    SHUTDOWN = 5

class TransitionStatus(IntEnum):
    """Статус перехода FSM"""
    UNSPECIFIED = 0
    SUCCESS = 1
    FAILED = 2
    PENDING = 3

def _validate_fsm_state(value: Any) -> FsmState:
    """Валидация значения FsmState"""
    if isinstance(value, FsmState):
        return value
    elif isinstance(value, int):
        try:
            return FsmState(value)
        except ValueError:
            raise ValueError(f"Invalid FsmState value: {value}")
    else:
        raise TypeError(f"Expected FsmState or int, got {type(value)}")

def _validate_string(value: Any, field_name: str) -> str:
    """Валидация строкового значения"""
    if value is None:
        return ""
    elif isinstance(value, str):
        return value
    else:
        logger.warning(f"Converting {field_name} to string: {value}")
        return str(value)

def _validate_int(value: Any, field_name: str, default: int = 0) -> int:
    """Валидация целочисленного значения"""
    if value is None:
        return default
    elif isinstance(value, int):
        return value
    elif isinstance(value, (float, str)):
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Using default for {field_name}: {value}")
            return default
    else:
        logger.warning(f"Using default for {field_name}: {value}")
        return default

def _validate_float(value: Any, field_name: str, default: float = 0.0) -> float:
    """Валидация числового значения"""
    if value is None:
        return default
    elif isinstance(value, (int, float)):
        return float(value)
    elif isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Using default for {field_name}: {value}")
            return default
    else:
        logger.warning(f"Using default for {field_name}: {value}")
        return default

@dataclass(frozen=True)
class TransitionDTO:
    """DTO для перехода состояния FSM (immutable)"""
    from_state: FsmState
    to_state: FsmState
    trigger_event: str
    status: TransitionStatus = TransitionStatus.SUCCESS
    error_message: str = ""
    ts_mono: float = 0.0
    ts_wall: float = 0.0
    
    def __post_init__(self):
        # Валидация входных данных
        object.__setattr__(self, 'from_state', _validate_fsm_state(self.from_state))
        object.__setattr__(self, 'to_state', _validate_fsm_state(self.to_state))
        object.__setattr__(self, 'trigger_event', _validate_string(self.trigger_event, "trigger_event"))
        object.__setattr__(self, 'status', TransitionStatus(self.status) if not isinstance(self.status, TransitionStatus) else self.status)
        object.__setattr__(self, 'error_message', _validate_string(self.error_message, "error_message"))
        object.__setattr__(self, 'ts_mono', _validate_float(self.ts_mono, "ts_mono"))
        object.__setattr__(self, 'ts_wall', _validate_float(self.ts_wall, "ts_wall"))
            
        # Устанавливаем временные метки если не заданы
        if self.ts_mono == 0.0:
            object.__setattr__(self, 'ts_mono', time.monotonic())
        if self.ts_wall == 0.0:
            object.__setattr__(self, 'ts_wall', time.time())
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь"""
        return {
            'from_state': self.from_state.value,
            'to_state': self.to_state.value,
            'trigger_event': self.trigger_event,
            'status': self.status.value,
            'error_message': self.error_message,
            'ts_mono': self.ts_mono,
            'ts_wall': self.ts_wall
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TransitionDTO':
        """Создание из словаря"""
        return cls(
            from_state=_validate_fsm_state(data.get('from_state', FsmState.UNSPECIFIED)),
            to_state=_validate_fsm_state(data.get('to_state', FsmState.UNSPECIFIED)),
            trigger_event=_validate_string(data.get('trigger_event', ''), 'trigger_event'),
            status=TransitionStatus(data.get('status', TransitionStatus.UNSPECIFIED)),
            error_message=_validate_string(data.get('error_message', ''), 'error_message'),
            ts_mono=_validate_float(data.get('ts_mono', 0.0), 'ts_mono'),
            ts_wall=_validate_float(data.get('ts_wall', 0.0), 'ts_wall')
        )
    
    def to_json(self) -> str:
        """Конвертация в JSON"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'TransitionDTO':
        """Создание из JSON"""
        data = json.loads(json_str)
        return cls.from_dict(data)

@dataclass(frozen=True)
class FsmSnapshotDTO:
    """
    DTO для снапшота FSM состояния (immutable).
    Внутренняя модель без protobuf зависимостей.
    """
    # Обязательные поля
    version: int
    state: FsmState
    reason: str = ""
    
    # Временные метки
    ts_mono: float = 0.0  # monotonic time для порядка
    ts_wall: float = 0.0  # wall clock time для логов
    
    # Опциональные поля
    snapshot_id: str = ""
    prev_state: Optional[FsmState] = None
    fsm_instance_id: str = ""
    source_module: str = "fsm_handler"
    attempt_count: int = 0
    
    # История переходов и метаданные
    history: List[TransitionDTO] = None
    context_data: Dict[str, str] = None
    state_metadata: Dict[str, str] = None
    
    def __post_init__(self):
        # Валидация входных данных
        object.__setattr__(self, 'version', _validate_int(self.version, "version"))
        object.__setattr__(self, 'state', _validate_fsm_state(self.state))
        object.__setattr__(self, 'reason', _validate_string(self.reason, "reason"))
        object.__setattr__(self, 'ts_mono', _validate_float(self.ts_mono, "ts_mono"))
        object.__setattr__(self, 'ts_wall', _validate_float(self.ts_wall, "ts_wall"))
        object.__setattr__(self, 'snapshot_id', _validate_string(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, 'prev_state', _validate_fsm_state(self.prev_state) if self.prev_state is not None else None)
        object.__setattr__(self, 'fsm_instance_id', _validate_string(self.fsm_instance_id, "fsm_instance_id"))
        object.__setattr__(self, 'source_module', _validate_string(self.source_module, "source_module"))
        object.__setattr__(self, 'attempt_count', _validate_int(self.attempt_count, "attempt_count"))
        
        # Устанавливаем значения по умолчанию для mutable полей
        if self.history is None:
            object.__setattr__(self, 'history', [])
        if self.context_data is None:
            object.__setattr__(self, 'context_data', {})
        if self.state_metadata is None:
            object.__setattr__(self, 'state_metadata', {})
            
        # Валидация коллекций
        if not isinstance(self.history, list):
            object.__setattr__(self, 'history', [])
        if not isinstance(self.context_data, dict):
            object.__setattr__(self, 'context_data', {})
        if not isinstance(self.state_metadata, dict):
            object.__setattr__(self, 'state_metadata', {})
            
        # Устанавливаем временные метки если не заданы
        if self.ts_mono == 0.0:
            object.__setattr__(self, 'ts_mono', time.monotonic())
        if self.ts_wall == 0.0:
            object.__setattr__(self, 'ts_wall', time.time())
            
        # Генерируем ID если не задан
        if not self.snapshot_id:
            object.__setattr__(self, 'snapshot_id', str(uuid.uuid4()))
        if not self.fsm_instance_id:
            object.__setattr__(self, 'fsm_instance_id', str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь"""
        return {
            'version': self.version,
            'state': self.state.value,
            'reason': self.reason,
            'ts_mono': self.ts_mono,
            'ts_wall': self.ts_wall,
            'snapshot_id': self.snapshot_id,
            'prev_state': self.prev_state.value if self.prev_state else None,
            'fsm_instance_id': self.fsm_instance_id,
            'source_module': self.source_module,
            'attempt_count': self.attempt_count,
            'history': [h.to_dict() for h in self.history],
            'context_data': self.context_data,
            'state_metadata': self.state_metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FsmSnapshotDTO':
        """Создание из словаря"""
        history = []
        if 'history' in data:
            for h_data in data['history']:
                history.append(TransitionDTO.from_dict(h_data))
        
        return cls(
            version=_validate_int(data.get('version', 0), 'version'),
            state=_validate_fsm_state(data.get('state', FsmState.UNSPECIFIED)),
            reason=_validate_string(data.get('reason', ''), 'reason'),
            ts_mono=_validate_float(data.get('ts_mono', 0.0), 'ts_mono'),
            ts_wall=_validate_float(data.get('ts_wall', 0.0), 'ts_wall'),
            snapshot_id=_validate_string(data.get('snapshot_id', ''), 'snapshot_id'),
            prev_state=_validate_fsm_state(data.get('prev_state')) if data.get('prev_state') is not None else None,
            fsm_instance_id=_validate_string(data.get('fsm_instance_id', ''), 'fsm_instance_id'),
            source_module=_validate_string(data.get('source_module', 'fsm_handler'), 'source_module'),
            attempt_count=_validate_int(data.get('attempt_count', 0), 'attempt_count'),
            history=history,
            context_data=data.get('context_data', {}),
            state_metadata=data.get('state_metadata', {})
        )
    
    def to_json(self) -> str:
        """Конвертация в JSON"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'FsmSnapshotDTO':
        """Создание из JSON"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def is_valid(self) -> bool:
        """Проверка валидности снапшота"""
        try:
            # Проверяем основные поля
            if not isinstance(self.version, int) or self.version < 0:
                return False
            if not isinstance(self.state, FsmState):
                return False
            if not isinstance(self.reason, str):
                return False
                
            # Проверяем временные метки
            if not isinstance(self.ts_mono, (int, float)) or self.ts_mono < 0:
                return False
            if not isinstance(self.ts_wall, (int, float)) or self.ts_wall < 0:
                return False
                
            # Проверяем UUID
            try:
                uuid.UUID(self.snapshot_id)
                uuid.UUID(self.fsm_instance_id)
            except (ValueError, TypeError):
                return False
                
            # Проверяем коллекции
            if not isinstance(self.history, list):
                return False
            if not isinstance(self.context_data, dict):
                return False
            if not isinstance(self.state_metadata, dict):
                return False
                
            # Проверяем историю переходов
            for transition in self.history:
                if not isinstance(transition, TransitionDTO):
                    return False
                    
            return True
        except Exception:
            return False

def initial_snapshot() -> FsmSnapshotDTO:
    """Создаёт начальный снапшот для COLD_START"""
    now_mono = time.monotonic()
    now_wall = time.time()
    
    return FsmSnapshotDTO(
        version=0,
        state=FsmState.BOOTING,
        prev_state=None,
        reason="COLD_START",
        ts_mono=now_mono,
        ts_wall=now_wall,
        source_module="initial_boot",
        attempt_count=0
    )

def create_transition(
    from_state: Union[FsmState, int],
    to_state: Union[FsmState, int],
    trigger: str,
    status: TransitionStatus = TransitionStatus.SUCCESS,
    error_msg: str = ""
) -> TransitionDTO:
    """Хелпер для создания перехода состояния"""
    return TransitionDTO(
        from_state=_validate_fsm_state(from_state),
        to_state=_validate_fsm_state(to_state),
        trigger_event=_validate_string(trigger, "trigger"),
        status=status if isinstance(status, TransitionStatus) else TransitionStatus(status),
        error_message=_validate_string(error_msg, "error_msg")
    )

def next_snapshot(
    current: FsmSnapshotDTO,
    new_state: Union[FsmState, int],
    reason: str,
    transition: Optional[TransitionDTO] = None
) -> FsmSnapshotDTO:
    """
    Создаёт новый снапшот на базе текущего с обновлённым состоянием.
    Увеличивает версию только при реальном изменении состояния.
    """
    # Валидация входных данных
    if not isinstance(current, FsmSnapshotDTO):
        raise TypeError(f"current must be FsmSnapshotDTO, got {type(current)}")
    
    new_state = _validate_fsm_state(new_state)
    reason = _validate_string(reason, "reason")
    
    version_increment = 1 if new_state != current.state else 0
    new_version = current.version + version_increment
    
    # Новая история переходов
    new_history = list(current.history) if current.history else []
    if transition:
        if not isinstance(transition, TransitionDTO):
            raise TypeError(f"transition must be TransitionDTO, got {type(transition)}")
        new_history.append(transition)
        
    return FsmSnapshotDTO(
        version=new_version,
        state=new_state,
        prev_state=current.state if new_state != current.state else current.prev_state,
        reason=reason,
        snapshot_id=str(uuid.uuid4()),  # новый ID для нового снапшота
        fsm_instance_id=current.fsm_instance_id,  # сохраняем instance ID
        source_module=current.source_module,
        attempt_count=current.attempt_count + (1 if new_state != current.state else 0),
        history=new_history,
        context_data=dict(current.context_data) if current.context_data else {},
        state_metadata=dict(current.state_metadata) if current.state_metadata else {}
    )

# Функции для работы с коллекциями
def merge_context_data(
    base: Dict[str, str], 
    override: Dict[str, str]
) -> Dict[str, str]:
    """Объединение контекстных данных"""
    result = dict(base) if base else {}
    if override:
        result.update(override)
    return result

def filter_transitions_by_status(
    transitions: List[TransitionDTO], 
    status: TransitionStatus
) -> List[TransitionDTO]:
    """Фильтрация переходов по статусу"""
    return [t for t in transitions if t.status == status]

def get_latest_transitions(
    transitions: List[TransitionDTO], 
    count: int = 10
) -> List[TransitionDTO]:
    """Получение последних переходов"""
    return transitions[-count:] if len(transitions) > count else transitions

# Функции для проверки состояний
def is_terminal_state(state: FsmState) -> bool:
    """Проверка, является ли состояние терминальным"""
    return state in (FsmState.ERROR_STATE, FsmState.SHUTDOWN)

def is_active_state(state: FsmState) -> bool:
    """Проверка, является ли состояние активным"""
    return state == FsmState.ACTIVE

def is_stable_state(state: FsmState) -> bool:
    """Проверка, является ли состояние стабильным"""
    return state in (FsmState.IDLE, FsmState.ACTIVE)