"""
AsyncStateStore - потокобезопасное хранилище FSM состояний.
Single Source of Truth (SSOT) для FSM состояния в Q-Core процессе.
"""

import asyncio
from typing import Optional, List, Any, Dict
import logging
import time
from dataclasses import replace

from qiki.services.q_core_agent.state.types import FsmSnapshotDTO, initial_snapshot


logger = logging.getLogger(__name__)


class StateStoreError(Exception):
    """Базовое исключение для ошибок StateStore"""

    pass


class StateVersionError(StateStoreError):
    """Ошибка версионирования состояния"""

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

    def __init__(self, initial_state: Optional[FsmSnapshotDTO] = None):
        self._lock = asyncio.Lock()
        self._snap: Optional[FsmSnapshotDTO] = initial_state
        self._subscribers: List[asyncio.Queue] = []
        self._subscriber_ids: Dict[int, str] = {}  # для отладки
        self._metrics: Dict[str, Any] = {
            "total_sets": 0,
            "total_gets": 0,
            "version_conflicts": 0,
            "subscriber_count": 0,
            "last_update_ts": 0.0,
            "creation_ts": time.time(),
        }

    async def get(self) -> Optional[FsmSnapshotDTO]:
        """
        Получить текущий снапшот состояния.
        Возвращает immutable DTO или None если состояние не инициализировано.
        """
        async with self._lock:
            self._metrics["total_gets"] += 1
            # DTO уже immutable, можно возвращать как есть
            return self._snap

    async def get_with_meta(self) -> tuple[Optional[FsmSnapshotDTO], Dict[str, Any]]:
        """Получить состояние с метаинформацией"""
        async with self._lock:
            self._metrics["total_gets"] += 1
            meta = {
                "store_metrics": dict(self._metrics),
                "subscriber_count": len(self._subscribers),
                "has_state": self._snap is not None,
                "current_version": self._snap.version if self._snap else -1,
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
        """
        if new_snap is None:
            raise StateStoreError("Попытка установить None состояние")

        async with self._lock:
            # Проверка версионности
            if enforce_version and self._snap is not None:
                if new_snap.version <= self._snap.version:
                    self._metrics["version_conflicts"] += 1
                    raise StateVersionError(f"Версия {new_snap.version} не больше текущей {self._snap.version}")

            # Автоинкремент версии если нужно
            if self._snap is not None and new_snap.version <= self._snap.version:
                # Создаём новый снапшот с корректной версией
                new_snap = replace(new_snap, version=self._snap.version + 1)

            self._snap = new_snap
            self._metrics["total_sets"] += 1
            self._metrics["last_update_ts"] = time.time()

            # Уведомляем подписчиков
            await self._notify_subscribers(new_snap)

            logger.debug(
                f"StateStore updated: version={new_snap.version}, "
                f"state={getattr(new_snap.state, 'name', new_snap.state)}, reason='{new_snap.reason}'"
            )

            return self._snap

    async def subscribe(self, subscriber_id: str = "unknown") -> asyncio.Queue:
        """
        Подписаться на изменения состояния.

        Returns:
            asyncio.Queue с FsmSnapshotDTO объектами при изменениях
        """
        queue = asyncio.Queue(maxsize=64)

        async with self._lock:
            self._subscribers.append(queue)
            queue_id = id(queue)
            self._subscriber_ids[queue_id] = subscriber_id
            self._metrics["subscriber_count"] = len(self._subscribers)

            # Отправляем текущее состояние новому подписчику
            if self._snap is not None:
                try:
                    queue.put_nowait(self._snap)
                except asyncio.QueueFull:
                    logger.warning(f"Queue full for new subscriber {subscriber_id}")

            logger.debug(f"New subscriber: {subscriber_id}, total: {len(self._subscribers)}")

        return queue

    async def unsubscribe(self, queue: asyncio.Queue):
        """Отписаться от уведомлений"""
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)
                queue_id = id(queue)
                subscriber_id = self._subscriber_ids.pop(queue_id, "unknown")
                self._metrics["subscriber_count"] = len(self._subscribers)
                logger.debug(f"Unsubscribed: {subscriber_id}, remaining: {len(self._subscribers)}")

    async def _notify_subscribers(self, snap: FsmSnapshotDTO):
        """Уведомить всех подписчиков о новом состоянии"""
        dead_queues = []

        for queue in self._subscribers:
            try:
                queue.put_nowait(snap)
            except asyncio.QueueFull:
                # Очередь переполнена - логируем но не блокируем
                queue_id = id(queue)
                subscriber_id = self._subscriber_ids.get(queue_id, "unknown")
                logger.warning(f"Subscriber {subscriber_id} queue full, skipping update")
            except Exception as e:
                # Очередь мертва - помечаем для удаления
                queue_id = id(queue)
                subscriber_id = self._subscriber_ids.get(queue_id, "unknown")
                logger.warning(f"Dead subscriber {subscriber_id}: {e}")
                dead_queues.append(queue)

        # Удаляем мертвые очереди
        for dead_queue in dead_queues:
            try:
                self._subscribers.remove(dead_queue)
                queue_id = id(dead_queue)
                self._subscriber_ids.pop(queue_id, None)
            except ValueError:
                pass  # Уже удалена

        if dead_queues:
            self._metrics["subscriber_count"] = len(self._subscribers)

    async def initialize_if_empty(self) -> FsmSnapshotDTO:
        """Инициализировать начальным состоянием если пусто"""
        async with self._lock:
            if self._snap is None:
                self._snap = initial_snapshot()
                self._metrics["total_sets"] += 1
                self._metrics["last_update_ts"] = time.time()

                # Уведомляем подписчиков
                await self._notify_subscribers(self._snap)

                logger.info("StateStore initialized with COLD_START state")

            return self._snap

    async def get_metrics(self) -> Dict[str, Any]:
        """Получить метрики работы StateStore"""
        async with self._lock:
            uptime = time.time() - self._metrics["creation_ts"]
            current_state_name = self._snap.state.name if self._snap else "UNINITIALIZED"
            return {
                **self._metrics,
                "uptime_seconds": uptime,
                "current_version": self._snap.version if self._snap else -1,
                "current_state": current_state_name,
                "active_subscribers": len(self._subscribers),
            }

    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья StateStore"""
        metrics = await self.get_metrics()

        health = {"healthy": True, "issues": [], "metrics": metrics}

        # Проверки здоровья
        if metrics["version_conflicts"] > metrics["total_sets"] * 0.1:
            health["healthy"] = False
            health["issues"].append("Высокий процент конфликтов версий")

        if len(self._subscribers) > 100:
            health["issues"].append("Много подписчиков, возможна утечка")

        if self._snap is None:
            health["healthy"] = False
            health["issues"].append("StateStore не инициализирован")

        return health


# Удобные функции для создания store
def create_store(initial_state: Optional[FsmSnapshotDTO] = None) -> AsyncStateStore:
    """Создать новый AsyncStateStore"""
    return AsyncStateStore(initial_state)


def create_initialized_store() -> AsyncStateStore:
    """Создать StateStore с начальным состоянием COLD_START"""
    return AsyncStateStore(initial_snapshot())


# Константы для тестирования
TEST_SUBSCRIBER_TIMEOUT = 5.0  # таймаут для тестовых подписчиков
MAX_QUEUE_SIZE = 64  # размер очереди подписчиков
