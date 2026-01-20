# Анализ файла fsm_handler.py

## Вход и цель
- **Файл**: fsm_handler.py
- **Итог**: Обзор обработчика конечного автомата агента

## Сбор контекста
- **Исходник**: src/qiki/services/q_core_agent/core/fsm_handler.py
- **Связанные файлы**:
  - services/q_core_agent/core/interfaces.py (интерфейс IFSMHandler)
  - services/q_core_agent/core/agent.py (основной агент и контекст)
  - services/q_core_agent/core/agent_logger.py (логирование)
  - services/q_core_agent/state/types.py (DTO типы FSM)
  - services/q_core_agent/state/conv.py (конвертеры)
  - services/q_core_agent/state/store.py (хранилище состояний)
  - generated/fsm_state_pb2.py (protobuf типы FSM)

**[Факт]**: Файл реализует обработчик конечного автомата агента с поддержкой как новой архитектуры StateStore, так и legacy protobuf режима.

## Локализация артефакта
- **Точный путь**: src/qiki/services/q_core_agent/core/fsm_handler.py
- **Окружение**: Python 3.x, typing, asyncio

## Фактический разбор
### Ключевые классы и функции:
- **FSMHandler**: Основной класс обработчика FSM, реализует интерфейс IFSMHandler
  - `__init__()`: Инициализация обработчика с контекстом и StateStore
  - `process_fsm_dto()`: Асинхронный метод обработки FSM через DTO и StateStore
  - `_compute_transition_dto()`: Вычисление переходов FSM на основе DTO
  - `process_fsm_state()`: Синхронный метод обработки FSM через protobuf (legacy)

### Логика переходов FSM:
1. **BOOTING → IDLE**: При успешной инициализации BIOS (BOOT_COMPLETE)
2. **BOOTING → ERROR_STATE**: При ошибке BIOS (BIOS_ERROR)
3. **IDLE → ACTIVE**: При наличии предложений (PROPOSALS_RECEIVED)
4. **IDLE → ERROR_STATE**: При ошибке BIOS (BIOS_ERROR)
5. **ACTIVE → IDLE**: При отсутствии предложений (NO_PROPOSALS)
6. **ACTIVE → ERROR_STATE**: При ошибке BIOS (BIOS_ERROR)
7. **ERROR_STATE → IDLE**: При восстановлении BIOS и отсутствии предложений (ERROR_CLEARED)

**[Факт]**: Обработчик поддерживает две версии реализации FSM: новую через DTO/StateStore и legacy через protobuf.

## Роль в системе и связи
- **Как участвует в потоке**: Обрабатывает переходы конечного автомата агента на основе состояния BIOS и наличия предложений
- **Кто вызывает**: TickOrchestrator через методы агента
- **Что от него ждут**: Корректная обработка состояний FSM и запись результатов в StateStore
- **Чем он рискует**: Неправильные переходы могут привести к нестабильной работе агента

**[Факт]**: FSMHandler является ключевым компонентом для управления состоянием агента.

## Несоответствия и риски
1. **Средний риск**: Дублирование логики переходов в двух методах (_compute_transition_dto и legacy логика)
2. **Средний риск**: При ошибке записи в StateStore обработчик продолжает работу без уведомления вызывающего кода
3. **Низкий риск**: Нет явной обработки исключений в _compute_transition_dto
4. **Низкий риск**: Нет тестов для проверки всех возможных переходов FSM

**[Гипотеза]**: Может потребоваться унификация логики переходов и улучшение обработки ошибок.

## Мини-патчи (safe-fix)
**[Патч]**: Улучшить обработку ошибок при записи в StateStore:
```python
# Записываем в StateStore если доступен
if self.state_store:
    try:
        stored_dto = await self.state_store.set(new_dto)
        logger.debug(f"FSM state stored: version={stored_dto.version}, state={stored_dto.state.name}")
        return stored_dto
    except Exception as e:
        logger.error(f"Failed to store FSM state: {e}")
        # Продолжаем работать без StateStore, но уведомляем вызывающий код
        # Например, можно бросить исключение или вернуть специальный флаг
        # raise RuntimeError(f"Failed to store FSM state: {e}") from e
```

## Рефактор-скетч (по желанию)
```python
from typing import Dict, Any, TYPE_CHECKING, Optional
from .interfaces import IFSMHandler
from .agent_logger import logger

if TYPE_CHECKING:
    from .agent import AgentContext
    from ..state.store import AsyncStateStore

# StateStore imports
from ..state.types import (
    FsmSnapshotDTO, TransitionDTO, FsmState, TransitionStatus,
    create_transition, next_snapshot
)
from ..state.conv import dto_to_proto

# Legacy protobuf imports (только для совместимости)
from generated.fsm_state_pb2 import FsmStateSnapshot, StateTransition, FSMStateEnum
from google.protobuf.timestamp_pb2 import Timestamp

class FSMTransitionError(Exception):
    """Исключение для ошибок переходов FSM"""
    pass

class FSMHandler(IFSMHandler):
    """
    Handles the Finite State Machine (FSM) logic for the Q-Core Agent.
    This handler is responsible for processing the current FSM state,
    evaluating conditions, and determining the next state.
    
    StateStore integration: единственный писатель FSM состояний.
    """
    
    def __init__(self, context: "AgentContext", state_store: Optional["AsyncStateStore"] = None):
        self.context = context
        self.state_store = state_store
        logger.info(f"FSMHandler initialized with StateStore: {state_store is not None}")
    
    async def process_fsm_dto(self, current_dto: FsmSnapshotDTO) -> FsmSnapshotDTO:
        """
        Новый метод для работы с DTO и StateStore.
        Обрабатывает переходы FSM и записывает результат в StateStore.
        """
        # Проверка параметров
        if not isinstance(current_dto, FsmSnapshotDTO):
            raise TypeError("current_dto must be FsmSnapshotDTO instance")
            
        logger.debug(f"Processing FSM DTO state: {current_dto.state.name}")

        try:
            # Получаем условия для переходов
            bios_ok = self.context.is_bios_ok()
            has_proposals = self.context.has_valid_proposals()

            # Определяем новое состояние и причину перехода
            new_state, trigger_event = self._compute_transition_dto(
                current_dto.state, bios_ok, has_proposals
            )

            # Создаём переход если состояние изменилось
            transition = None
            if new_state != current_dto.state:
                logger.info(f"FSM Transition: {current_dto.state.name} -> {new_state.name} (Trigger: {trigger_event})")
                transition = create_transition(
                    from_state=current_dto.state,
                    to_state=new_state,
                    trigger=trigger_event,
                    status=TransitionStatus.SUCCESS
                )

            # Создаём новый снапшот
            new_dto = next_snapshot(
                current=current_dto,
                new_state=new_state,
                reason=trigger_event if transition else current_dto.reason,
                transition=transition
            )

            # Записываем в StateStore если доступен
            if self.state_store:
                stored_dto = await self._store_fsm_state(new_dto)
                return stored_dto

            logger.debug(f"FSM new DTO state: {new_dto.state.name}")
            return new_dto
            
        except Exception as e:
            logger.error(f"Error processing FSM DTO: {e}")
            raise FSMTransitionError(f"Failed to process FSM state: {e}") from e
    
    async def _store_fsm_state(self, dto: FsmSnapshotDTO) -> FsmSnapshotDTO:
        """Сохранение состояния FSM в StateStore с обработкой ошибок"""
        try:
            stored_dto = await self.state_store.set(dto)
            logger.debug(f"FSM state stored: version={stored_dto.version}, state={stored_dto.state.name}")
            return stored_dto
        except Exception as e:
            logger.error(f"Failed to store FSM state: {e}")
            # Можно добавить логику повторных попыток или fallback
            raise
    
    def _compute_transition_dto(self, current_state: FsmState, bios_ok: bool, has_proposals: bool) -> tuple[FsmState, str]:
        """Вычисляет следующее состояние на основе текущего и условий"""
        # Валидация параметров
        if not isinstance(current_state, FsmState):
            raise TypeError("current_state must be FsmState enum")
            
        try:
            if current_state == FsmState.BOOTING:
                if bios_ok:
                    return FsmState.IDLE, "BOOT_COMPLETE"
                else:
                    return FsmState.ERROR_STATE, "BIOS_ERROR"
            elif current_state == FsmState.IDLE:
                if not bios_ok:
                    return FsmState.ERROR_STATE, "BIOS_ERROR"
                elif has_proposals:
                    return FsmState.ACTIVE, "PROPOSALS_RECEIVED"
            elif current_state == FsmState.ACTIVE:
                if not bios_ok:
                    return FsmState.ERROR_STATE, "BIOS_ERROR"
                elif not has_proposals:
                    return FsmState.IDLE, "NO_PROPOSALS"
            elif current_state == FsmState.ERROR_STATE:
                if bios_ok and not has_proposals:
                    return FsmState.IDLE, "ERROR_CLEARED"

            # Нет изменения состояния
            return current_state, "NO_CHANGE"
            
        except Exception as e:
            logger.error(f"Error computing FSM transition: {e}")
            # В случае ошибки остаемся в текущем состоянии
            return current_state, "TRANSITION_ERROR"
    
    def process_fsm_state(self, current_fsm_state: FsmStateSnapshot) -> FsmStateSnapshot:
        """
        Legacy метод для обратной совместимости.
        Использует старую protobuf логику.
        """
        # Проверка параметров
        if not isinstance(current_fsm_state, FsmStateSnapshot):
            raise TypeError("current_fsm_state must be FsmStateSnapshot instance")
            
        logger.debug(f"Processing FSM state (legacy): {current_fsm_state.current_state}")

        next_state = FsmStateSnapshot()
        next_state.CopyFrom(current_fsm_state) # Start with a copy of the current state

        try:
            # State transition logic
            current_state = current_fsm_state.current_state
            bios_ok = self.context.is_bios_ok()
            has_proposals = self.context.has_valid_proposals()

            new_state_name, trigger_event = self._compute_transition_protobuf(
                current_state, bios_ok, has_proposals
            )

            if new_state_name != current_state:
                logger.info(f"FSM Transition (legacy): {current_state} -> {new_state_name} (Trigger: {trigger_event})")
                new_transition = StateTransition(
                    from_state=current_state,
                    to_state=new_state_name,
                    trigger_event=trigger_event
                )
                new_transition.timestamp.GetCurrentTime()
                next_state.current_state = new_state_name
                next_state.history.append(new_transition)

            # Update timestamp for the new state snapshot
            next_state.timestamp.GetCurrentTime()

            logger.debug(f"FSM new state (legacy): {next_state.current_state}")
            return next_state
            
        except Exception as e:
            logger.error(f"Error processing legacy FSM state: {e}")
            # Возвращаем исходное состояние в случае ошибки
            return current_fsm_state
    
    def _compute_transition_protobuf(self, current_state: FSMStateEnum, bios_ok: bool, has_proposals: bool) -> tuple[FSMStateEnum, str]:
        """Вычисляет следующее состояние на основе protobuf логики"""
        try:
            if current_state == FSMStateEnum.BOOTING:
                if bios_ok:
                    return FSMStateEnum.IDLE, "BOOT_COMPLETE"
                else:
                    return FSMStateEnum.ERROR_STATE, "BIOS_ERROR"
            elif current_state == FSMStateEnum.IDLE:
                if not bios_ok:
                    return FSMStateEnum.ERROR_STATE, "BIOS_ERROR"
                elif has_proposals:
                    return FSMStateEnum.ACTIVE, "PROPOSALS_RECEIVED"
            elif current_state == FSMStateEnum.ACTIVE:
                if not bios_ok:
                    return FSMStateEnum.ERROR_STATE, "BIOS_ERROR"
                elif not has_proposals:
                    return FSMStateEnum.IDLE, "NO_PROPOSALS"
            elif current_state == FSMStateEnum.ERROR_STATE:
                if bios_ok and not has_proposals:
                    return FSMStateEnum.IDLE, "ERROR_CLEARED"

            # Нет изменения состояния
            return current_state, "NO_CHANGE"
            
        except Exception as e:
            logger.error(f"Error computing legacy FSM transition: {e}")
            # В случае ошибки остаемся в текущем состоянии
            return current_state, "TRANSITION_ERROR"

    def _states_consistent(self, dto_state: FsmState, proto_state: FSMStateEnum) -> bool:
        """Проверка согласованности состояний между DTO и protobuf"""
        # Маппинг между состояниями
        state_mapping = {
            FsmState.UNSPECIFIED: FSMStateEnum.FSM_STATE_UNSPECIFIED,
            FsmState.BOOTING: FSMStateEnum.BOOTING,
            FsmState.IDLE: FSMStateEnum.IDLE,
            FsmState.ACTIVE: FSMStateEnum.ACTIVE,
            FsmState.ERROR_STATE: FSMStateEnum.ERROR_STATE,
            FsmState.SHUTDOWN: FSMStateEnum.SHUTDOWN,
        }
        
        return state_mapping.get(dto_state) == proto_state