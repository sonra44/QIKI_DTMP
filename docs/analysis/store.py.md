# Анализ файла store.py

## Вход и цель
- **Файл**: store.py
- **Итог**: Обзор асинхронного хранилища FSM состояний

## Сбор контекста
- **Исходник**: /home/sonra44/QIKI_DTMP/services/q_core_agent/state/store.py
- **Связанные файлы**:
  - services/q_core_agent/state/types.py (DTO типы FSM)
  - services/q_core_agent/state/conv.py (конвертеры)
  - services/q_core_agent/state/tests/test_store.py (тесты хранилища)
  - services/q_core_agent/core/fsm_handler.py (обработчик FSM)
  - services/q_core_agent/core/tick_orchestrator.py (оркестратор)

**[Факт]**: Файл реализует потокобезопасное асинхронное хранилище FSM состояний с поддержкой pub/sub механизма.

## Локализация артефакта
- **Точный путь**: /home/sonra44/QIKI_DTMP/services/q_core_agent/state/store.py
- **Окружение**: Python 3.x, asyncio, typing, dataclasses

## Фактический разбор
### Ключевые классы и функции:
- **StateStoreError**: Базовое исключение для ошибок StateStore
- **StateVersionError**: Исключение для ошибок версионирования состояния
- **AsyncStateStore**: Основной класс асинхронного хранилища состояний
  - `__init__()`: Инициализация хранилища с опциональным начальным состоянием
  - `get()`: Получение текущего состояния
  - `get_with_meta()`: Получение состояния с метаинформацией
  - `set()`: Установка нового состояния с версионированием
  - `subscribe()`: Подписка на изменения состояния
  - `unsubscribe()`: Отписка от уведомлений
  - `_notify_subscribers()`: Уведомление подписчиков о новых состояниях
  - `initialize_if_empty()`: Инициализация начальным состоянием если пусто
  - `get_metrics()`: Получение метрик работы хранилища
  - `health_check()`: Проверка здоровья хранилища
- **Вспомогательные функции**:
  - `create_store()`: Создание нового AsyncStateStore
  - `create_initialized_store()`: Создание инициализированного StateStore

### Ключевые принципы:
1. **Только один писатель**: FSMHandler как единственный писатель
2. **Множественные читатели**: Логи, gRPC, CLI и другие компоненты
3. **Pub/Sub через asyncio.Queue**: Механизм уведомлений подписчиков
4. **Версионирование**: Защита от дублирования и обеспечение порядка
5. **Иммутабельные DTO**: Безопасность данных через неизменяемость

**[Факт]**: Хранилище реализует принцип Single Source of Truth (SSOT) для FSM состояния в Q-Core процессе.

## Роль в системе и связи
- **Как участвует в потоке**: Хранит текущее состояние FSM и уведомляет подписчиков об изменениях
- **Кто вызывает**: FSMHandler (писатель), другие компоненты (читатели)
- **Что от него ждут**: Потокобезопасное хранение состояний, надежное уведомление подписчиков, сбор метрик
- **Чем он рискует**: Блокировки при высокой нагрузке, утечки памяти при неправильной отписке

**[Факт]**: AsyncStateStore является критически важным компонентом для координации состояния агента.

## Несоответствия и риски
1. **Средний риск**: При переполнении очереди подписчика обновление пропускается без уведомления
2. **Средний риск**: Лимит подписчиков есть, но его значение и поведение при превышении нужно явно документировать (исключение/метрики)
3. **Низкий риск**: Нет механизма автоматической очистки неактивных подписчиков
4. **Низкий риск**: Нет поддержки персистентности состояний (только in-memory)

**[Гипотеза]**: Может потребоваться добавить механизм персистентности и улучшить управление подписчиками.

## Мини-патчи (safe-fix)
**[Патч]**: Улучшить обработку переполнения очереди подписчиков:
```python
async def _notify_subscribers(self, snap: FsmSnapshotDTO):
    """Уведомить всех подписчиков о новом состоянии"""
    dead_queues = []
    
    for queue in self._subscribers:
        try:
            # Используем put с таймаутом вместо put_nowait
            try:
                await asyncio.wait_for(queue.put(snap), timeout=0.1)
            except asyncio.TimeoutError:
                # Очередь переполнена - логируем и продолжаем
                queue_id = id(queue)
                subscriber_id = self._subscriber_ids.get(queue_id, "unknown")
                logger.warning(f"Subscriber {subscriber_id} queue timeout, update may be delayed")
                
        except Exception as e:
            # Очередь мертва - помечаем для удаления
            queue_id = id(queue)
            subscriber_id = self._subscriber_ids.get(queue_id, "unknown")
            logger.warning(f"Dead subscriber {subscriber_id}: {e}")
            dead_queues.append(queue)
            
    # Удаляем мертвые очереди
    if dead_queues:
        async with self._lock:
            for dead_queue in dead_queues:
                try:
                    self._subscribers.remove(dead_queue)
                    queue_id = id(dead_queue)
                    self._subscriber_ids.pop(queue_id, None)
                except ValueError:
                    pass  # Уже удалена
            
            if dead_queues:
                self._metrics['subscriber_count'] = len(self._subscribers)
```

## Рефактор-скетч (по желанию)
```python
"""
AsyncStateStore - потокобезопасное хранилище FSM состояний.
Single Source of Truth (SSOT) для FSM состояния в Q-Core процессе.
"""
import asyncio
from typing import Optional, List, Callable, Any, Dict, Set
import logging
import time
from dataclasses import replace
import weakref

from .types import FsmSnapshotDTO, initial_snapshot

logger = logging.getLogger(__name__)

class StateStoreError(Exception):
    """Базовое исключение для ошибок StateStore"""
    pass

class StateVersionError(StateStoreError):
    """Ошибка версионирования состояния"""
    pass

class SubscriberLimitError(StateStoreError):
    """Ошибка превышения лимита подписчиков"""
    pass

class AsyncStateStore:
    """
    Async-only StateStore для FSM состояния.
    
    Ключевые принципы:
    - Только один писатель (FSMHandler)
    - Множественные читатели (логи, gRPC, CLI)
    - Pub/Sub через asyncio.Queue для подписчиков
    - Версионирование и защита от дублирования
    - Иммутабельные DTO снапшоты
    """
    
    # Константы по умолчанию
    DEFAULT_MAX_SUBSCRIBERS = 1000
    DEFAULT_QUEUE_SIZE = 64
    DEFAULT_NOTIFICATION_TIMEOUT = 1.0  # секунды
    
    def __init__(
        self, 
        initial_state: Optional[FsmSnapshotDTO] = None,
        max_subscribers: int = DEFAULT_MAX_SUBSCRIBERS,
        queue_size: int = DEFAULT_QUEUE_SIZE
    ):
        self._lock = asyncio.Lock()
        self._snap: Optional[FsmSnapshotDTO] = initial_state
        self._subscribers: List[asyncio.Queue] = []
        self._subscriber_ids: Dict[int, str] = {}  # для отладки
        self._max_subscribers = max_subscribers
        self._queue_size = queue_size
        
        self._metrics: Dict[str, Any] = {
            'total_sets': 0,
            'total_gets': 0,
            'version_conflicts': 0,
            'subscriber_count': 0,
            'last_update_ts': 0.0,
            'creation_ts': time.time(),
            'notifications_sent': 0,
            'notifications_failed': 0,
            'dead_subscribers_removed': 0
        }
        
        # Для отслеживания активности
        self._last_health_check = time.time()
    
    async def get(self) -> Optional[FsmSnapshotDTO]:
        """
        Получить текущий снапшот состояния.
        Возвращает immutable DTO или None если состояние не инициализировано.
        """
        async with self._lock:
            self._metrics['total_gets'] += 1
            # DTO уже immutable, можно возвращать как есть
            return self._snap
    
    async def get_with_meta(self) -> tuple[Optional[FsmSnapshotDTO], Dict[str, Any]]:
        """Получить состояние с метаинформацией"""
        async with self._lock:
            self._metrics['total_gets'] += 1
            meta = {
                'store_metrics': dict(self._metrics),
                'subscriber_count': len(self._subscribers),
                'has_state': self._snap is not None,
                'current_version': self._snap.version if self._snap else -1,
                'max_subscribers': self._max_subscribers,
                'queue_size': self._queue_size
            }
            return self._snap, meta
            
    async def set(self, new_snap: FsmSnapshotDTO, enforce_version: bool = False) -> FsmSnapshotDTO:
        """
        Установить новое состояние.
        
        Args:
            new_snap: Новый снапшот состояния
            enforce_version: Если True, проверяет что версия новее текущей
            
        Returns:
            Установленный снапшот (может отличаться от входного по версии)
            
        Raises:
            StateVersionError: При нарушении версионности
            StateStoreError: При других ошибках
        """
        # Валидация входных данных
        if new_snap is None:
            raise StateStoreError("Попытка установить None состояние")
        
        if not isinstance(new_snap, FsmSnapshotDTO):
            raise StateStoreError(f"Ожидается FsmSnapshotDTO, получено {type(new_snap)}")
            
        async with self._lock:
            try:
                # Проверка версионности
                if enforce_version and self._snap is not None:
                    if new_snap.version <= self._snap.version:
                        self._metrics['version_conflicts'] += 1
                        raise StateVersionError(
                            f"Версия {new_snap.version} не больше текущей {self._snap.version}"
                        )
                
                # Автоинкремент версии если нужно
                final_snap = new_snap
                if self._snap is not None and new_snap.version <= self._snap.version:
                    # Создаём новый снапшот с корректной версией
                    final_snap = replace(new_snap, version=self._snap.version + 1)
                
                self._snap = final_snap
                self._metrics['total_sets'] += 1
                self._metrics['last_update_ts'] = time.time()
                
                # Уведомляем подписчиков
                await self._notify_subscribers(final_snap)
                
                logger.debug(
                    f"StateStore updated: version={final_snap.version}, "
                    f"state={final_snap.state.name}, reason='{final_snap.reason}'"
                )
                
                return self._snap
                
            except StateVersionError:
                # Перебрасываем как есть
                raise
            except Exception as e:
                logger.error(f"Error setting state: {e}")
                raise StateStoreError(f"Ошибка установки состояния: {e}") from e
    
    async def subscribe(self, subscriber_id: str = "unknown", max_queue_size: Optional[int] = None) -> asyncio.Queue:
        """
        Подписаться на изменения состояния.
        
        Returns:
            asyncio.Queue с FsmSnapshotDTO объектами при изменениях
            
        Raises:
            SubscriberLimitError: При превышении лимита подписчиков
        """
        # Проверка лимита подписчиков
        async with self._lock:
            if len(self._subscribers) >= self._max_subscribers:
                raise SubscriberLimitError(
                    f"Превышен лимит подписчиков: {len(self._subscribers)} >= {self._max_subscribers}"
                )
        
        queue_size = max_queue_size or self._queue_size
        queue = asyncio.Queue(maxsize=queue_size)
        
        async with self._lock:
            self._subscribers.append(queue)
            queue_id = id(queue)
            self._subscriber_ids[queue_id] = subscriber_id
            self._metrics['subscriber_count'] = len(self._subscribers)
            
            # Отправляем текущее состояние новому подписчику
            if self._snap is not None:
                try:
                    queue.put_nowait(self._snap)
                except asyncio.QueueFull:
                    logger.warning(f"Queue full for new subscriber {subscriber_id}")
                    
            logger.debug(f"New subscriber: {subscriber_id}, total: {len(self._subscribers)}")
            
        return queue
        
    async def unsubscribe(self, queue: asyncio.Queue) -> bool:
        """Отписаться от уведомлений"""
        if not isinstance(queue, asyncio.Queue):
            logger.warning(f"Invalid queue type for unsubscribe: {type(queue)}")
            return False
            
        async with self._lock:
            if queue in self._subscribers:
                try:
                    self._subscribers.remove(queue)
                    queue_id = id(queue)
                    subscriber_id = self._subscriber_ids.pop(queue_id, "unknown")
                    self._metrics['subscriber_count'] = len(self._subscribers)
                    logger.debug(f"Unsubscribed: {subscriber_id}, remaining: {len(self._subscribers)}")
                    return True
                except Exception as e:
                    logger.error(f"Error unsubscribing: {e}")
                    return False
            else:
                logger.debug("Queue not found in subscribers list")
                return False
    
    async def _notify_subscribers(self, snap: FsmSnapshotDTO):
        """Уведомить всех подписчиков о новом состоянии"""
        if not self._subscribers:
            return
            
        dead_queues = []
        notifications_sent = 0
        notifications_failed = 0
        
        for queue in self._subscribers:
            try:
                # Используем put с таймаутом вместо put_nowait
                try:
                    await asyncio.wait_for(queue.put(snap), timeout=self.DEFAULT_NOTIFICATION_TIMEOUT)
                    notifications_sent += 1
                except asyncio.TimeoutError:
                    # Очередь переполнена - логируем
                    queue_id = id(queue)
                    subscriber_id = self._subscriber_ids.get(queue_id, "unknown")
                    logger.warning(f"Subscriber {subscriber_id} queue timeout, update may be delayed")
                    notifications_failed += 1
                    
            except Exception as e:
                # Очередь мертва - помечаем для удаления
                queue_id = id(queue)
                subscriber_id = self._subscriber_ids.get(queue_id, "unknown")
                logger.warning(f"Dead subscriber {subscriber_id}: {e}")
                dead_queues.append(queue)
                notifications_failed += 1
                
        # Обновляем метрики
        self._metrics['notifications_sent'] += notifications_sent
        self._metrics['notifications_failed'] += notifications_failed
        
        # Удаляем мертвые очереди
        if dead_queues:
            async with self._lock:
                removed_count = 0
                for dead_queue in dead_queues:
                    try:
                        self._subscribers.remove(dead_queue)
                        queue_id = id(dead_queue)
                        self._subscriber_ids.pop(queue_id, None)
                        removed_count += 1
                    except ValueError:
                        pass  # Уже удалена
                
                if removed_count > 0:
                    self._metrics['dead_subscribers_removed'] += removed_count
                    self._metrics['subscriber_count'] = len(self._subscribers)
                    logger.info(f"Removed {removed_count} dead subscribers")
    
    async def initialize_if_empty(self) -> FsmSnapshotDTO:
        """Инициализировать начальным состоянием если пусто"""
        async with self._lock:
            if self._snap is None:
                try:
                    self._snap = initial_snapshot()
                    self._metrics['total_sets'] += 1
                    self._metrics['last_update_ts'] = time.time()
                    
                    # Уведомляем подписчиков
                    await self._notify_subscribers(self._snap)
                    
                    logger.info("StateStore initialized with COLD_START state")
                    
                except Exception as e:
                    logger.error(f"Error initializing state store: {e}")
                    raise StateStoreError(f"Ошибка инициализации хранилища: {e}") from e
                    
            return self._snap
            
    async def get_metrics(self) -> Dict[str, Any]:
        """Получить метрики работы StateStore"""
        async with self._lock:
            uptime = time.time() - self._metrics['creation_ts']
            return {
                **self._metrics,
                'uptime_seconds': uptime,
                'current_version': self._snap.version if self._snap else -1,
                'current_state': self._snap.state.name if self._snap else "UNINITIALIZED",
                'active_subscribers': len(self._subscribers),
                'max_subscribers': self._max_subscribers,
                'queue_size': self._queue_size
            }
            
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья StateStore"""
        self._last_health_check = time.time()
        metrics = await self.get_metrics()
        
        health = {
            'healthy': True,
            'issues': [],
            'warnings': [],
            'metrics': metrics,
            'timestamp': self._last_health_check
        }
        
        # Проверки здоровья
        if metrics['version_conflicts'] > metrics['total_sets'] * 0.1:
            health['healthy'] = False
            health['issues'].append("Высокий процент конфликтов версий")
            
        if len(self._subscribers) > self._max_subscribers * 0.8:
            health['warnings'].append("Много подписчиков, возможна утечка")
            
        if self._snap is None:
            health['healthy'] = False
            health['issues'].append("StateStore не инициализирован")
            
        # Проверка активности
        time_since_last_update = time.time() - metrics['last_update_ts']
        if time_since_last_update > 60:  # больше минуты
            health['warnings'].append("Давно не было обновлений состояния")
            
        return health
    
    async def cleanup(self):
        """Очистка ресурсов"""
        async with self._lock:
            # Очищаем подписчиков
            self._subscribers.clear()
            self._subscriber_ids.clear()
            self._metrics['subscriber_count'] = 0
            logger.info("StateStore cleaned up")
    
    async def get_subscriber_info(self) -> Dict[str, Any]:
        """Получить информацию о подписчиках"""
        async with self._lock:
            return {
                'total_subscribers': len(self._subscribers),
                'subscriber_ids': list(self._subscriber_ids.values()),
                'max_subscribers': self._max_subscribers,
                'queue_size': self._queue_size
            }

# Удобные функции для создания store
def create_store(
    initial_state: Optional[FsmSnapshotDTO] = None,
    max_subscribers: int = AsyncStateStore.DEFAULT_MAX_SUBSCRIBERS,
    queue_size: int = AsyncStateStore.DEFAULT_QUEUE_SIZE
) -> AsyncStateStore:
    """Создать новый AsyncStateStore"""
    return AsyncStateStore(initial_state, max_subscribers, queue_size)

def create_initialized_store(
    max_subscribers: int = AsyncStateStore.DEFAULT_MAX_SUBSCRIBERS,
    queue_size: int = AsyncStateStore.DEFAULT_QUEUE_SIZE
) -> AsyncStateStore:
    """Создать StateStore с начальным состоянием COLD_START"""
    return AsyncStateStore(initial_snapshot(), max_subscribers, queue_size)

# Функции для мониторинга
async def monitor_state_store(store: AsyncStateStore, interval: float = 30.0):
    """Мониторинг состояния хранилища"""
    while True:
        try:
            health = await store.health_check()
            if not health['healthy']:
                logger.warning(f"StateStore health issues: {health['issues']}")
            if health['warnings']:
                logger.info(f"StateStore warnings: {health['warnings']}")
                
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("StateStore monitoring cancelled")
            break
        except Exception as e:
            logger.error(f"Error in state store monitoring: {e}")
            await asyncio.sleep(interval)

# Константы для тестирования
TEST_SUBSCRIBER_TIMEOUT = 5.0  # таймаут для тестовых подписчиков
MAX_QUEUE_SIZE = 64  # размер очереди подписчиков