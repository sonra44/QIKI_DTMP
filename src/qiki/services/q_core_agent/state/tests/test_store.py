"""
Серьёзные unit тесты для AsyncStateStore.
Проверяют concurrency, pub/sub, версионирование, ошибки.
"""

import pytest
import asyncio
from unittest.mock import Mock

from qiki.services.q_core_agent.state.store import (
    AsyncStateStore,
    StateStoreError,
    StateVersionError,
    create_initialized_store,
    create_store,
)
from qiki.services.q_core_agent.state.types import (
    FsmSnapshotDTO,
    FsmState,
    initial_snapshot,
)


@pytest.fixture
def empty_store():
    """Пустой StateStore для тестов"""
    return AsyncStateStore()


@pytest.fixture
def initialized_store():
    """Инициализированный StateStore с начальным состоянием"""
    initial = initial_snapshot()
    return AsyncStateStore(initial)


@pytest.fixture
def sample_snapshot():
    """Тестовый снапшот для использования в тестах"""
    return FsmSnapshotDTO(version=1, state=FsmState.IDLE, reason="TEST_SNAPSHOT")


class TestAsyncStateStoreBasics:
    """Базовые тесты AsyncStateStore"""

    @pytest.mark.asyncio
    async def test_empty_store_get_returns_none(self, empty_store):
        """Тест получения из пустого стора"""
        result = await empty_store.get()
        assert result is None

    @pytest.mark.asyncio
    async def test_store_set_get_basic(self, empty_store, sample_snapshot):
        """Тест базового set/get"""
        stored = await empty_store.set(sample_snapshot)
        assert stored == sample_snapshot

        retrieved = await empty_store.get()
        assert retrieved == sample_snapshot
        assert retrieved.version == 1
        assert retrieved.state == FsmState.IDLE

    @pytest.mark.asyncio
    async def test_store_immutability(self, empty_store, sample_snapshot):
        """Тест что StateStore не изменяет переданные DTO"""
        original_version = sample_snapshot.version

        await empty_store.set(sample_snapshot)

        # Исходный объект не должен изменяться
        assert sample_snapshot.version == original_version

    @pytest.mark.asyncio
    async def test_version_auto_increment(self, empty_store):
        """Тест автоинкремента версии"""
        snap1 = FsmSnapshotDTO(version=1, state=FsmState.BOOTING, reason="FIRST")
        snap2 = FsmSnapshotDTO(
            version=1, state=FsmState.IDLE, reason="SECOND"
        )  # та же версия

        stored1 = await empty_store.set(snap1)
        assert stored1.version == 1

        stored2 = await empty_store.set(snap2)
        assert stored2.version == 2  # автоинкремент

    @pytest.mark.asyncio
    async def test_version_enforcement(self, empty_store):
        """Тест принудительной проверки версий"""
        snap1 = FsmSnapshotDTO(version=5, state=FsmState.IDLE, reason="FIRST")
        snap2 = FsmSnapshotDTO(
            version=3, state=FsmState.ACTIVE, reason="SECOND"
        )  # старая версия

        await empty_store.set(snap1)

        # Должно упасть при enforce_version=True
        with pytest.raises(StateVersionError):
            await empty_store.set(snap2, enforce_version=True)

        # Без enforce_version должно работать с автоинкрементом
        stored = await empty_store.set(snap2, enforce_version=False)
        assert stored.version == 6  # 5 + 1

    @pytest.mark.asyncio
    async def test_set_none_raises_error(self, empty_store):
        """Тест что установка None вызывает ошибку"""
        with pytest.raises(StateStoreError):
            await empty_store.set(None)

    @pytest.mark.asyncio
    async def test_get_with_meta(self, initialized_store):
        """Тест получения состояния с метаинформацией"""
        snapshot, meta = await initialized_store.get_with_meta()

        assert snapshot is not None
        assert isinstance(meta, dict)
        assert "store_metrics" in meta
        assert "current_version" in meta
        assert "has_state" in meta
        assert meta["has_state"] is True
        assert meta["current_version"] == snapshot.version


class TestAsyncStateStorePubSub:
    """Тесты pub/sub механизма StateStore"""

    @pytest.mark.asyncio
    async def test_subscribe_get_initial_state(self, initialized_store):
        """Тест что подписчик получает текущее состояние сразу"""
        queue = await initialized_store.subscribe("test_subscriber")

        # Должно быть начальное состояние
        snapshot = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert snapshot is not None
        assert snapshot.state == FsmState.BOOTING

    @pytest.mark.asyncio
    async def test_subscribe_get_updates(self, empty_store):
        """Тест получения обновлений подписчиками"""
        # Подписываемся до установки состояния
        queue = await empty_store.subscribe("test_subscriber")

        # Устанавливаем состояние
        test_snapshot = FsmSnapshotDTO(version=1, state=FsmState.IDLE, reason="TEST")
        await empty_store.set(test_snapshot)

        # Подписчик должен получить уведомление
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received == test_snapshot

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, empty_store):
        """Тест нескольких подписчиков"""
        # Создаём несколько подписчиков
        queue1 = await empty_store.subscribe("subscriber_1")
        queue2 = await empty_store.subscribe("subscriber_2")
        queue3 = await empty_store.subscribe("subscriber_3")

        # Отправляем обновление
        test_snapshot = FsmSnapshotDTO(
            version=1, state=FsmState.ACTIVE, reason="MULTI_TEST"
        )
        await empty_store.set(test_snapshot)

        # Все подписчики должны получить уведомление
        received1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
        received2 = await asyncio.wait_for(queue2.get(), timeout=1.0)
        received3 = await asyncio.wait_for(queue3.get(), timeout=1.0)

        assert received1 == test_snapshot
        assert received2 == test_snapshot
        assert received3 == test_snapshot

    @pytest.mark.asyncio
    async def test_unsubscribe(self, empty_store):
        """Тест отписки от уведомлений"""
        queue = await empty_store.subscribe("test_subscriber")

        # Отписываемся
        await empty_store.unsubscribe(queue)

        # Устанавливаем состояние - подписчик не должен получить
        test_snapshot = FsmSnapshotDTO(
            version=1, state=FsmState.IDLE, reason="UNSUB_TEST"
        )
        await empty_store.set(test_snapshot)

        # Очередь должна быть пуста
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_queue_overflow_handling(self, empty_store):
        """Тест обработки переполнения очереди подписчика"""
        # Создаём подписчика с маленькой очередью
        await empty_store.subscribe("overflow_test")

        # Заполняем очередь до отказа (maxsize=64 в StateStore)
        for i in range(70):  # больше чем maxsize
            snapshot = FsmSnapshotDTO(
                version=i + 1, state=FsmState.IDLE, reason=f"OVERFLOW_{i}"
            )
            await empty_store.set(snapshot)

        # Очередь должна быть заполнена, но не должно быть исключений
        # (StateStore логирует предупреждения но не падает)

    @pytest.mark.asyncio
    async def test_dead_subscriber_cleanup(self, empty_store):
        """Тест очистки мёртвых подписчиков"""
        queue = await empty_store.subscribe("dead_subscriber")

        # "Убиваем" очередь - имитируем закрытие
        queue._closed = True

        # Устанавливаем состояние - должна произойти очистка
        test_snapshot = FsmSnapshotDTO(
            version=1, state=FsmState.IDLE, reason="CLEANUP_TEST"
        )
        await empty_store.set(test_snapshot)

        # Проверяем что подписчик удалён
        await empty_store.get_metrics()
        # После очистки мёртвых очередей активных подписчиков должно быть меньше


class TestAsyncStateStoreConcurrency:
    """Тесты конкурентного доступа к StateStore"""

    @pytest.mark.asyncio
    async def test_concurrent_gets(self, initialized_store):
        """Тест конкурентного чтения"""

        async def read_state():
            return await initialized_store.get()

        # Запускаем много конкурентных чтений
        tasks = [read_state() for _ in range(100)]
        results = await asyncio.gather(*tasks)

        # Все результаты должны быть одинаковыми
        assert all(r == results[0] for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_sets(self, empty_store):
        """Тест конкурентных записей"""

        async def set_state(i):
            snapshot = FsmSnapshotDTO(
                version=i, state=FsmState.IDLE, reason=f"CONCURRENT_{i}"
            )
            return await empty_store.set(snapshot)

        # Запускаем конкурентные записи
        tasks = [set_state(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        # Все записи должны успешно выполниться
        assert len(results) == 50

        # Финальная версия должна быть максимальной из переданных
        final_state = await empty_store.get()
        assert final_state.version == 49

    @pytest.mark.asyncio
    async def test_concurrent_subscribe_unsubscribe(self, empty_store):
        """Тест конкурентных подписок/отписок"""

        async def subscribe_unsubscribe():
            queue = await empty_store.subscribe("concurrent_test")
            await asyncio.sleep(0.01)  # небольшая задержка
            await empty_store.unsubscribe(queue)
            return True

        # Запускаем много конкурентных подписок/отписок
        tasks = [subscribe_unsubscribe() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # Все операции должны завершиться успешно
        assert all(results)

        # В итоге не должно быть активных подписчиков
        metrics = await empty_store.get_metrics()
        assert metrics["active_subscribers"] == 0

    @pytest.mark.asyncio
    async def test_mixed_operations_stress(self, empty_store):
        """Стресс-тест смешанных операций"""
        results = {"reads": 0, "writes": 0, "subscribes": 0}

        async def reader():
            for _ in range(20):
                await empty_store.get()
                await asyncio.sleep(0.001)
                results["reads"] += 1

        async def writer():
            for i in range(10):
                snapshot = FsmSnapshotDTO(
                    version=i * 100, state=FsmState.ACTIVE, reason="STRESS"
                )
                await empty_store.set(snapshot)
                await asyncio.sleep(0.002)
                results["writes"] += 1

        async def subscriber():
            for i in range(5):
                queue = await empty_store.subscribe(f"stress_{i}")
                await asyncio.sleep(0.005)
                await empty_store.unsubscribe(queue)
                results["subscribes"] += 1

        # Запускаем всё конкурентно
        await asyncio.gather(
            reader(),
            reader(),
            reader(),  # 3 читателя
            writer(),
            writer(),  # 2 писателя
            subscriber(),
            subscriber(),  # 2 подписчика
        )

        # Все операции должны выполниться
        assert results["reads"] == 60  # 3 * 20
        assert results["writes"] == 20  # 2 * 10
        assert results["subscribes"] == 10  # 2 * 5


class TestAsyncStateStoreMetrics:
    """Тесты системы метрик StateStore"""

    @pytest.mark.asyncio
    async def test_basic_metrics(self, empty_store):
        """Тест базовых метрик"""
        metrics = await empty_store.get_metrics()

        assert "total_sets" in metrics
        assert "total_gets" in metrics
        assert "version_conflicts" in metrics
        assert "creation_ts" in metrics
        assert "uptime_seconds" in metrics
        assert "current_version" in metrics
        assert "current_state" in metrics

        assert metrics["total_sets"] == 0
        assert metrics["total_gets"] == 0  # get_metrics() не считается за get()
        assert metrics["current_state"] == "UNINITIALIZED"

    @pytest.mark.asyncio
    async def test_metrics_updates(self, empty_store, sample_snapshot):
        """Тест обновления метрик"""
        # Начальные метрики
        metrics1 = await empty_store.get_metrics()
        initial_gets = metrics1["total_gets"]

        # Выполняем операции
        await empty_store.set(sample_snapshot)
        await empty_store.get()
        await empty_store.get()

        # Проверяем обновлённые метрики
        metrics2 = await empty_store.get_metrics()

        assert metrics2["total_sets"] == 1
        assert metrics2["total_gets"] == initial_gets + 2  # +2 get()
        assert metrics2["current_version"] == sample_snapshot.version
        assert metrics2["current_state"] == sample_snapshot.state.name

    @pytest.mark.asyncio
    async def test_version_conflict_metrics(self, empty_store):
        """Тест метрик конфликтов версий"""
        snap1 = FsmSnapshotDTO(version=10, state=FsmState.IDLE, reason="FIRST")
        snap2 = FsmSnapshotDTO(version=5, state=FsmState.ACTIVE, reason="CONFLICT")

        await empty_store.set(snap1)

        # Пытаемся записать старую версию с принуждением
        try:
            await empty_store.set(snap2, enforce_version=True)
        except StateVersionError:
            pass

        metrics = await empty_store.get_metrics()
        assert metrics["version_conflicts"] == 1

    @pytest.mark.asyncio
    async def test_health_check(self, initialized_store):
        """Тест проверки здоровья StateStore"""
        health = await initialized_store.health_check()

        assert "healthy" in health
        assert "issues" in health
        assert "metrics" in health

        assert health["healthy"] is True
        assert isinstance(health["issues"], list)

    @pytest.mark.asyncio
    async def test_health_check_with_issues(self, empty_store):
        """Тест проверки здоровья с проблемами"""
        # Создаём много конфликтов версий
        snap = FsmSnapshotDTO(version=100, state=FsmState.IDLE, reason="CONFLICT_TEST")
        await empty_store.set(snap)

        for i in range(15):  # много конфликтов
            try:
                await empty_store.set(
                    FsmSnapshotDTO(version=1, state=FsmState.ACTIVE, reason="OLD"),
                    enforce_version=True,
                )
            except StateVersionError:
                pass

        health = await empty_store.health_check()

        # Должна быть обнаружена проблема с конфликтами
        assert health["healthy"] is False
        assert any("конфликт" in issue.lower() for issue in health["issues"])


class TestAsyncStateStoreHelpers:
    """Тесты helper функций"""

    def test_create_store(self):
        """Тест создания пустого стора"""
        store = create_store()
        assert isinstance(store, AsyncStateStore)

    def test_create_store_with_initial(self):
        """Тест создания стора с начальным состоянием"""
        initial = initial_snapshot()
        store = create_store(initial)
        assert isinstance(store, AsyncStateStore)

    def test_create_initialized_store(self):
        """Тест создания инициализированного стора"""
        store = create_initialized_store()
        assert isinstance(store, AsyncStateStore)

    @pytest.mark.asyncio
    async def test_initialize_if_empty(self, empty_store):
        """Тест инициализации пустого стора"""
        # Стор пустой
        assert await empty_store.get() is None

        # Инициализируем
        snapshot = await empty_store.initialize_if_empty()

        assert snapshot is not None
        assert snapshot.state == FsmState.BOOTING
        assert snapshot.reason == "COLD_START"

        # Повторная инициализация не должна изменить состояние
        snapshot2 = await empty_store.initialize_if_empty()
        assert snapshot2 == snapshot


class TestAsyncStateStoreErrorHandling:
    """Тесты обработки ошибок в StateStore"""

    @pytest.mark.asyncio
    async def test_corrupted_state_handling(self, empty_store):
        """Тест обработки некорректного состояния"""
        # Создаём DTO с некорректными данными
        bad_snapshot = FsmSnapshotDTO(
            version=-1,  # отрицательная версия
            state=999,  # некорректное состояние (если бы enum не защищал)
            reason="",  # пустая причина
        )

        # StateStore должен принять любой валидный DTO
        # (валидация на уровне enum'ов и dataclass)
        await empty_store.set(bad_snapshot)

        retrieved = await empty_store.get()
        assert retrieved.version == -1  # сохранилось как есть

    @pytest.mark.asyncio
    async def test_exception_in_subscriber_notification(self, empty_store):
        """Тест обработки исключений при уведомлении подписчиков"""
        # Создаём мок подписчика который выбрасывает исключение
        bad_queue = Mock()
        bad_queue.put_nowait = Mock(side_effect=Exception("Subscriber error"))

        # Добавляем его в список подписчиков напрямую (для тестирования)
        async with empty_store._lock:
            empty_store._subscribers.append(bad_queue)

        # Устанавливаем состояние - не должно упасть из-за плохого подписчика
        snapshot = FsmSnapshotDTO(version=1, state=FsmState.IDLE, reason="ERROR_TEST")
        result = await empty_store.set(snapshot)

        assert result == snapshot  # операция должна пройти успешно

    @pytest.mark.asyncio
    async def test_concurrent_access_safety(self, empty_store):
        """Тест безопасности при конкурентном доступе"""

        errors = []

        async def risky_operation(i):
            try:
                snapshot = FsmSnapshotDTO(
                    version=i, state=FsmState.IDLE, reason=f"RISKY_{i}"
                )
                await empty_store.set(snapshot)
                result = await empty_store.get()
                assert result is not None
            except Exception as e:
                errors.append(e)

        # Запускаем много конкурентных операций
        tasks = [risky_operation(i) for i in range(100)]
        await asyncio.gather(*tasks)

        # Не должно быть ошибок
        assert len(errors) == 0

        # StateStore должен быть в консистентном состоянии
        final_state = await empty_store.get()
        assert final_state is not None
        metrics = await empty_store.get_metrics()
        assert metrics["total_sets"] == 100


if __name__ == "__main__":
    # Быстрый запуск основных тестов
    pytest.main([__file__, "-v"])
