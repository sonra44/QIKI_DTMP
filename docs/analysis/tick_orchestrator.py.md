# Анализ файла tick_orchestrator.py

## Вход и цель
- **Файл**: tick_orchestrator.py
- **Итог**: Обзор оркестратора циклов обработки агента

## Сбор контекста
- **Исходник**: src/qiki/services/q_core_agent/core/tick_orchestrator.py
- **Связанные файлы**:
  - services/q_core_agent/core/agent.py (основной агент)
  - services/q_core_agent/core/interfaces.py (интерфейсы)
  - services/q_core_agent/core/agent_logger.py (логирование)
  - services/q_core_agent/core/fsm_handler.py (обработчик FSM)
  - services/q_core_agent/state/store.py (хранилище состояний)
  - services/q_core_agent/state/types.py (DTO типы)
  - services/q_core_agent/state/conv.py (конвертеры)

**[Факт]**: Файл реализует оркестратор выполнения циклов обработки агента с поддержкой как синхронного, так и асинхронного режимов.

## Локализация артефакта
- **Точный путь**: src/qiki/services/q_core_agent/core/tick_orchestrator.py
- **Окружение**: Python 3.x, asyncio, typing

## Фактический разбор
### Ключевые классы и функции:
- **TickOrchestrator**: Основной класс оркестратора
  - `__init__()`: Инициализация оркестратора с агентом, конфигурацией и StateStore
  - `run_tick_async()`: Асинхронный метод выполнения цикла обработки с StateStore
  - `_handle_fsm_with_state_store()`: Обработка FSM с использованием StateStore
  - `run_tick()`: Синхронный метод выполнения цикла обработки (legacy)

### Фазы выполнения цикла:
1. **Update Context**: Обновление контекста агента из провайдера данных
2. **Handle BIOS**: Обработка статуса BIOS через BiosHandler
3. **Handle FSM**: Обработка состояния конечного автомата
4. **Evaluate Proposals**: Оценка предложений через ProposalEvaluator
5. **Make Decision**: Принятие решений и отправка команд актуаторам

**[Факт]**: Оркестратор поддерживает два режима работы: с StateStore (новый асинхронный) и без него (legacy синхронный).

## Роль в системе и связи
- **Как участвует в потоке**: Координирует выполнение всех этапов обработки в одном цикле агента
- **Кто вызывает**: QCoreAgent через метод run_tick()
- **Что от него ждут**: Структурированное выполнение всех фаз обработки с логированием и обработкой ошибок
- **Чем он рискует**: Сбои в любой фазе могут привести к переходу в безопасный режим

**[Факт]**: Оркестратор обеспечивает структурированное выполнение циклов обработки с поддержкой новой архитектуры StateStore.

## Несоответствия и риски
1. **Высокий риск**: Метод run_tick_async() fallback на синхронный метод без await, что может привести к неправильной работе
2. **Средний риск**: При ошибке в _handle_fsm_with_state_store() происходит fallback на старый метод без proper error handling
3. **Низкий риск**: Нет явной проверки типов параметров в методах
4. **Низкий риск**: Нет явной документации по ожидаемому формату конфигурации

**[Гипотеза]**: Может потребоваться унификация асинхронного и синхронного режимов работы.

## Мини-патчи (safe-fix)
**[Патч]**: Исправить fallback в run_tick_async():
```python
async def run_tick_async(self, data_provider: IDataProvider):
    """
    Новый асинхронный метод для работы с StateStore.
    """
    if not self.use_state_store or not self.state_store:
        # Fallback на синхронный метод с предупреждением
        logger.warning("StateStore not available, falling back to sync mode")
        await asyncio.to_thread(self.run_tick, data_provider)
        return

    # Остальной код метода...
```

## Рефактор-скетч (по желанию)
```python
from typing import Any, Dict, TYPE_CHECKING, Optional
import time
import os
import asyncio
from .agent_logger import logger
from .interfaces import IDataProvider

if TYPE_CHECKING:
    from .agent import QCoreAgent
    from ..state.store import AsyncStateStore

# StateStore imports
from ..state.types import FsmSnapshotDTO, initial_snapshot
from ..state.conv import dto_to_proto

class TickOrchestrator:
    """
    Orchestrates the execution of a single agent tick, handling error recovery and structured logging.
    StateStore integration: координирует работу с новой архитектурой состояний.
    """
    
    def __init__(self, agent: "QCoreAgent", config: Dict[str, Any], state_store: Optional["AsyncStateStore"] = None):
        self.agent = agent
        self.config = config or {}
        self.state_store = state_store
        self.errors_count = 0
        self.use_state_store = os.getenv('QIKI_USE_STATESTORE', 'false').lower() == 'true'
        logger.info(f"TickOrchestrator initialized with StateStore: {self.state_store is not None}, enabled: {self.use_state_store}")
    
    async def run_tick_async(self, data_provider: IDataProvider):
        """
        Новый асинхронный метод для работы с StateStore.
        """
        # Проверка параметров
        if not isinstance(data_provider, IDataProvider):
            raise TypeError("data_provider must implement IDataProvider interface")
            
        if not self.use_state_store or not self.state_store:
            # Fallback на синхронный метод с предупреждением
            logger.warning("StateStore not available or not enabled, falling back to sync mode")
            await asyncio.to_thread(self.run_tick, data_provider)
            return

        start_time = time.time()
        self.agent.tick_id += 1
        logger.info("--- Async Tick Start ---", extra={
            "tick_id": self.agent.tick_id
        })
        
        try:
            # Фазы выполнения
            phase_results = await self._execute_phases(data_provider)
            
            tick_duration = time.time() - start_time
            self._log_tick_completion(tick_duration, phase_results)
            
        except Exception as e:
            await self._handle_tick_error(e)
    
    async def _execute_phases(self, data_provider: IDataProvider) -> Dict[str, float]:
        """Выполнение всех фаз цикла обработки"""
        phase_durations = {}
        
        # Phase 1: Update Context (без FSM из провайдера)
        phase_durations["update_context"] = await self._execute_phase(
            "update_context",
            lambda: self.agent._update_context_without_fsm(data_provider)
        )

        # Phase 2: Handle BIOS
        phase_durations["handle_bios"] = await self._execute_phase(
            "handle_bios",
            self.agent._handle_bios
        )

        # Phase 3: Handle FSM через StateStore
        phase_durations["handle_fsm"] = await self._execute_phase(
            "handle_fsm",
            self._handle_fsm_with_state_store
        )

        # Phase 4: Evaluate Proposals
        phase_durations["evaluate_proposals"] = await self._execute_phase(
            "evaluate_proposals",
            self.agent._evaluate_proposals
        )

        # Phase 5: Make Decision
        phase_durations["make_decision"] = await self._execute_phase(
            "make_decision",
            self.agent._make_decision
        )
        
        return phase_durations
    
    async def _execute_phase(self, phase_name: str, phase_func) -> float:
        """Выполнение одной фазы с измерением времени"""
        start_time = time.time()
        try:
            result = phase_func()
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Phase '{phase_name}' failed: {e}")
            raise
        return time.time() - start_time
    
    def _log_tick_completion(self, tick_duration: float, phase_durations: Dict[str, float]):
        """Логирование завершения цикла обработки"""
        logger.info("Async Tick complete", extra={
            "tick_id": self.agent.tick_id,
            "bios_ok": self.agent.context.bios_status.all_systems_go if self.agent.context.bios_status else None,
            "fsm_state": self.agent.context.fsm_state.current_state if self.agent.context.fsm_state else None,
            "proposals_count": len(self.agent.context.proposals),
            "tick_duration_ms": round(tick_duration * 1000, 2),
            "errors_count": self.errors_count,
            "phase_durations_ms": {
                phase: round(duration * 1000, 2)
                for phase, duration in phase_durations.items()
            }
        })
    
    async def _handle_tick_error(self, error: Exception):
        """Обработка ошибок цикла обработки"""
        self.errors_count += 1
        logger.error(f"Async Tick failed: {error}")
        self.agent._switch_to_safe_mode()
        
        recovery_delay = self.config.get("recovery_delay", 2)
        if recovery_delay > 0:
            await asyncio.sleep(recovery_delay)
    
    async def _handle_fsm_with_state_store(self):
        """Обработка FSM с использованием StateStore"""
        try:
            # Получаем текущее состояние из StateStore
            current_dto = await self.state_store.get()
            
            if current_dto is None:
                # Инициализируем StateStore если пуст
                current_dto = await self.state_store.initialize_if_empty()
                logger.info("StateStore initialized with COLD_START")
            
            # Обрабатываем FSM переходы через новый метод
            updated_dto = await self.agent.fsm_handler.process_fsm_dto(current_dto)
            
            # Конвертируем в protobuf для контекста (для совместимости с логами)
            self.agent.context.fsm_state = dto_to_proto(updated_dto)
            
            logger.debug(f"FSM processed: v={updated_dto.version}, state={updated_dto.state.name}")
            
        except Exception as e:
            logger.error(f"FSM StateStore processing failed: {e}")
            # Fallback на старый метод
            self.agent._handle_fsm()
    
    def run_tick(self, data_provider: IDataProvider):
        """
        Legacy синхронный метод для обратной совместимости.
        """
        # Проверка параметров
        if not isinstance(data_provider, IDataProvider):
            raise TypeError("data_provider must implement IDataProvider interface")
            
        start_time = time.time()
        self.agent.tick_id += 1
        logger.info("--- Tick Start (Legacy) ---", extra={
            "tick_id": self.agent.tick_id
        })
        
        try:
            # Фазы выполнения (синхронные)
            phase_durations = self._execute_phases_sync(data_provider)
            
            tick_duration = time.time() - start_time
            self._log_tick_completion_sync(tick_duration, phase_durations)
            
        except Exception as e:
            self._handle_tick_error_sync(e)
    
    def _execute_phases_sync(self, data_provider: IDataProvider) -> Dict[str, float]:
        """Выполнение всех фаз в синхронном режиме"""
        phase_durations = {}
        
        # Phase 1: Update Context
        phase_durations["update_context"] = self._execute_phase_sync(
            lambda: self.agent._update_context(data_provider)
        )

        # Phase 2: Handle BIOS
        phase_durations["handle_bios"] = self._execute_phase_sync(
            self.agent._handle_bios
        )

        # Phase 3: Handle FSM
        phase_durations["handle_fsm"] = self._execute_phase_sync(
            self.agent._handle_fsm
        )

        # Phase 4: Evaluate Proposals
        phase_durations["evaluate_proposals"] = self._execute_phase_sync(
            self.agent._evaluate_proposals
        )

        # Phase 5: Make Decision
        phase_durations["make_decision"] = self._execute_phase_sync(
            self.agent._make_decision
        )
        
        return phase_durations
    
    def _execute_phase_sync(self, phase_func) -> float:
        """Выполнение одной фазы в синхронном режиме"""
        start_time = time.time()
        try:
            phase_func()
        except Exception as e:
            logger.error(f"Phase failed: {e}")
            raise
        return time.time() - start_time
    
    def _log_tick_completion_sync(self, tick_duration: float, phase_durations: Dict[str, float]):
        """Логирование завершения цикла обработки в синхронном режиме"""
        logger.info("Tick complete (Legacy)", extra={
            "tick_id": self.agent.tick_id,
            "bios_ok": self.agent.context.bios_status.all_systems_go if self.agent.context.bios_status else None,
            "fsm_state": self.agent.context.fsm_state.current_state if self.agent.context.fsm_state else None,
            "proposals_count": len(self.agent.context.proposals),
            "tick_duration_ms": round(tick_duration * 1000, 2),
            "errors_count": self.errors_count,
            "phase_durations_ms": {
                phase: round(duration * 1000, 2)
                for phase, duration in phase_durations.items()
            }
        })
    
    def _handle_tick_error_sync(self, error: Exception):
        """Обработка ошибок цикла обработки в синхронном режиме"""
        self.errors_count += 1
        logger.error(f"Tick failed (Legacy): {error}")
        self.agent._switch_to_safe_mode()
        
        recovery_delay = self.config.get("recovery_delay", 2)
        if recovery_delay > 0:
            time.sleep(recovery_delay)
```

## Примеры использования
```python
# Использование в основном агенте
from services.q_core_agent.core.tick_orchestrator import TickOrchestrator

# Создание оркестратора
orchestrator = TickOrchestrator(agent, config, state_store)

# Асинхронный запуск цикла обработки
await orchestrator.run_tick_async(data_provider)

# Синхронный запуск цикла обработки (legacy)
orchestrator.run_tick(data_provider)
```

```python
# Пример интеграции в тесты
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_tick_orchestrator_async():
    """Тест асинхронного оркестратора"""
    # Создаем моки
    mock_agent = Mock()
    mock_agent.tick_id = 0
    mock_agent.context = Mock()
    mock_agent.context.bios_status = Mock(all_systems_go=True)
    mock_agent.context.fsm_state = Mock(current_state="IDLE")
    mock_agent.context.proposals = []
    
    mock_data_provider = Mock()
    config = {"recovery_delay": 1}
    
    # Создаем оркестратор
    orchestrator = TickOrchestrator(mock_agent, config)
    
    # Запускаем цикл обработки
    await orchestrator.run_tick_async(mock_data_provider)
    
    # Проверяем что фазы были выполнены
    assert mock_agent._update_context_without_fsm.called
    assert mock_agent._handle_bios.called
    assert mock_agent._evaluate_proposals.called
    assert mock_agent._make_decision.called
```

## Тест-хуки/чек-лист
- [ ] Проверить инициализацию оркестратора с разными параметрами
- [ ] Проверить работу асинхронного режима с StateStore
- [ ] Проверить fallback на синхронный режим без StateStore
- [ ] Проверить корректность выполнения всех фаз обработки
- [ ] Проверить обработку ошибок в фазах
- [ ] Проверить логирование начала и завершения циклов
- [ ] Проверить переход в безопасный режим при ошибках
- [ ] Проверить работу с разными типами провайдеров данных
- [ ] Проверить корректность подсчета ошибок
- [ ] Проверить работу механизма восстановления

## Вывод
- **Текущее состояние**: Файл реализует оркестратор циклов обработки агента с поддержкой двух режимов работы
- **Что починить сразу**: Исправить fallback в run_tick_async() и добавить проверку типов параметров
- **Что отложить**: Унификацию асинхронного и синхронного режимов работы

**[Факт]**: Анализ завершен на основе содержимого файла и его роли в системе обработки агента.