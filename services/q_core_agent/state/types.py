"""
DTO модель для FSM состояний без зависимостей от protobuf.
Immutable dataclasses для безопасной работы с состоянием.
"""
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, List, Dict, Any
import time
import uuid


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
        # Устанавливаем временные метки если не заданы
        if self.ts_mono == 0.0:
            object.__setattr__(self, 'ts_mono', time.monotonic())
        if self.ts_wall == 0.0:
            object.__setattr__(self, 'ts_wall', time.time())


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
        # Устанавливаем значения по умолчанию для mutable полей
        if self.history is None:
            object.__setattr__(self, 'history', [])
        if self.context_data is None:
            object.__setattr__(self, 'context_data', {})
        if self.state_metadata is None:
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
    from_state: FsmState,
    to_state: FsmState,
    trigger: str,
    status: TransitionStatus = TransitionStatus.SUCCESS,
    error_msg: str = ""
) -> TransitionDTO:
    """Хелпер для создания перехода состояния"""
    return TransitionDTO(
        from_state=from_state,
        to_state=to_state,
        trigger_event=trigger,
        status=status,
        error_message=error_msg
    )


def next_snapshot(
    current: FsmSnapshotDTO,
    new_state: FsmState,
    reason: str,
    transition: Optional[TransitionDTO] = None
) -> FsmSnapshotDTO:
    """
    Создаёт новый снапшот на базе текущего с обновлённым состоянием.
    Увеличивает версию только при реальном изменении состояния.
    """
    version_increment = 1 if new_state != current.state else 0
    new_version = current.version + version_increment
    
    # Новая история переходов
    new_history = list(current.history) if current.history else []
    if transition:
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