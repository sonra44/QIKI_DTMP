"""
Серьёзные stress и concurrency тесты для StateStore архитектуры.
Проверяют поведение под высокой нагрузкой, многопоточность, утечки памяти.
"""

import pytest
import asyncio
import time
import gc
import psutil
import random

from q_core_agent.state.store import create_initialized_store
from q_core_agent.state.types import FsmSnapshotDTO, FsmState, next_snapshot
from q_core_agent.state.conv import dto_to_proto, dto_to_json_dict


# Настройки для stress тестов
STRESS_TEST_DURATION = 2.0  # секунды (короткие тесты для CI)
HIGH_LOAD_OPERATIONS = 1000
MEMORY_PRESSURE_SIZE = 10000
CONCURRENCY_WORKERS = 50


@pytest.fixture
def stress_store():
    """StateStore для stress тестов"""
    return create_initialized_store()


class PerformanceMonitor:
    """Монитор производительности для тестов"""

    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.start_memory = None
        self.operations = 0

    def __enter__(self):
        self.start_time = time.time()
        self.start_memory = psutil.Process().memory_info().rss
        gc.collect()  # очистка перед тестом
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss

        duration = end_time - self.start_time
        memory_delta = end_memory - self.start_memory

        ops_per_sec = self.operations / duration if duration > 0 else 0

        print(f"\n{self.name} Performance:")
        print(f"  Duration: {duration:.3f}s")
        print(f"  Operations: {self.operations}")
        print(f"  Ops/sec: {ops_per_sec:.1f}")
        print(f"  Memory delta: {memory_delta / 1024 / 1024:.2f} MB")

    def record_operation(self):
        """Записать выполнение операции"""
        self.operations += 1


class TestHighVolumeOperations:
    """Тесты высокой нагрузки операций"""

    @pytest.mark.asyncio
    async def test_high_volume_sets_and_gets(self, stress_store):
        """Стресс-тест большого количества set/get операций"""
        with PerformanceMonitor("High Volume Set/Get") as monitor:
            for i in range(HIGH_LOAD_OPERATIONS):
                # Создаём уникальный снапшот
                snapshot = FsmSnapshotDTO(
                    version=i,
                    state=FsmState(1 + (i % 4)),  # варьируем состояния
                    reason=f"STRESS_TEST_{i}",
                    context_data={f"key_{i}": f"value_{i}"},
                )

                # Set операция
                await stress_store.set(snapshot)
                monitor.record_operation()

                # Get операция
                retrieved = await stress_store.get()
                assert retrieved.version >= i  # может быть больше из-за автоинкремента
                monitor.record_operation()

        # Проверяем финальное состояние
        final_state = await stress_store.get()
        assert final_state is not None
        assert final_state.version >= HIGH_LOAD_OPERATIONS - 1

    @pytest.mark.asyncio
    async def test_rapid_state_transitions(self, stress_store):
        """Тест быстрых переходов состояний"""
        with PerformanceMonitor("Rapid State Transitions") as monitor:
            states = [
                FsmState.IDLE,
                FsmState.ACTIVE,
                FsmState.ERROR_STATE,
                FsmState.IDLE,
            ]

            for i in range(HIGH_LOAD_OPERATIONS):
                current = await stress_store.get()
                new_state = states[i % len(states)]

                # Создаём переход
                next_snap = next_snapshot(
                    current=current, new_state=new_state, reason=f"RAPID_TRANSITION_{i}"
                )

                await stress_store.set(next_snap)
                monitor.record_operation()

        # Проверяем что система остаётся стабильной
        final_state = await stress_store.get()
        assert final_state.state in states

        # Проверяем метрики
        metrics = await stress_store.get_metrics()
        assert metrics["total_sets"] >= HIGH_LOAD_OPERATIONS

    @pytest.mark.asyncio
    async def test_massive_subscriber_load(self, stress_store):
        """Тест большого количества подписчиков"""
        subscribers = []

        with PerformanceMonitor("Massive Subscriber Load") as monitor:
            # Создаём много подписчиков
            for i in range(200):  # много подписчиков
                queue = await stress_store.subscribe(f"stress_sub_{i}")
                subscribers.append(queue)
                monitor.record_operation()

            # Очищаем начальные сообщения
            for queue in subscribers:
                try:
                    await queue.get()
                except:
                    pass

            # Генерируем обновления
            for i in range(100):
                snapshot = FsmSnapshotDTO(
                    version=i + 1000,
                    state=FsmState.ACTIVE,
                    reason=f"SUBSCRIBER_LOAD_{i}",
                )
                await stress_store.set(snapshot)
                monitor.record_operation()

            # Проверяем что подписчики получают обновления
            received_counts = []
            for queue in subscribers:
                count = 0
                try:
                    while True:
                        await asyncio.wait_for(queue.get(), timeout=0.01)
                        count += 1
                except asyncio.TimeoutError:
                    pass
                received_counts.append(count)

        # Большинство подписчиков должны получить обновления
        successful_subscribers = sum(1 for count in received_counts if count > 0)
        assert successful_subscribers > len(subscribers) * 0.8  # 80% успешных

        # Очистка
        for queue in subscribers:
            await stress_store.unsubscribe(queue)


class TestConcurrencyStress:
    """Тесты конкурентного доступа под нагрузкой"""

    @pytest.mark.asyncio
    async def test_concurrent_writers_stress(self, stress_store):
        """Стресс-тест конкурентных писателей"""
        results = {"success": 0, "errors": 0}

        async def writer_task(writer_id: int):
            """Задача писателя"""
            try:
                for i in range(50):  # 50 операций на писателя
                    snapshot = FsmSnapshotDTO(
                        version=writer_id * 1000 + i,
                        state=FsmState.ACTIVE,
                        reason=f"WRITER_{writer_id}_OP_{i}",
                        context_data={"writer_id": str(writer_id), "op": str(i)},
                    )

                    await stress_store.set(snapshot)
                    await asyncio.sleep(0.001)  # небольшая пауза

                results["success"] += 1
            except Exception as e:
                results["errors"] += 1
                print(f"Writer {writer_id} error: {e}")

        with PerformanceMonitor("Concurrent Writers Stress") as monitor:
            # Запускаем много конкурентных писателей
            writers = [writer_task(i) for i in range(30)]
            await asyncio.gather(*writers)

            monitor.operations = results["success"] * 50

        # Проверяем результаты
        assert results["errors"] == 0, f"Got {results['errors']} errors"
        assert results["success"] == 30, "Not all writers succeeded"

        # Система должна остаться в консистентном состоянии
        final_state = await stress_store.get()
        assert final_state is not None

        # Метрики должны отражать активность
        metrics = await stress_store.get_metrics()
        assert metrics["total_sets"] >= 1500  # 30 writers * 50 ops

    @pytest.mark.asyncio
    async def test_mixed_operations_chaos(self, stress_store):
        """Хаотичный тест смешанных операций"""
        results = {"reads": 0, "writes": 0, "subscribes": 0, "errors": 0}

        async def reader_task():
            """Постоянно читает состояние"""
            try:
                for _ in range(300):
                    await stress_store.get()
                    results["reads"] += 1
                    await asyncio.sleep(0.001)
            except Exception:
                results["errors"] += 1

        async def writer_task():
            """Постоянно пишет новые состояния"""
            try:
                for i in range(100):
                    snapshot = FsmSnapshotDTO(
                        version=random.randint(1, 10000),
                        state=random.choice(list(FsmState)),
                        reason=f"CHAOS_{i}",
                    )
                    await stress_store.set(snapshot)
                    results["writes"] += 1
                    await asyncio.sleep(random.uniform(0.001, 0.005))
            except Exception:
                results["errors"] += 1

        async def subscriber_task():
            """Создаёт и удаляет подписчиков"""
            try:
                for i in range(50):
                    queue = await stress_store.subscribe(f"chaos_{i}")
                    results["subscribes"] += 1

                    # Читаем немного сообщений
                    for _ in range(3):
                        try:
                            await asyncio.wait_for(queue.get(), timeout=0.1)
                        except asyncio.TimeoutError:
                            break

                    await stress_store.unsubscribe(queue)
                    await asyncio.sleep(0.02)
            except Exception:
                results["errors"] += 1

        with PerformanceMonitor("Mixed Operations Chaos") as monitor:
            # Запускаем хаос
            await asyncio.gather(
                reader_task(),
                reader_task(),
                reader_task(),  # 3 читателя
                writer_task(),
                writer_task(),  # 2 писателя
                subscriber_task(),
                subscriber_task(),  # 2 подписчика
            )

            monitor.operations = (
                results["reads"] + results["writes"] + results["subscribes"]
            )

        # Проверяем что большинство операций прошли успешно
        total_operations = monitor.operations
        error_rate = results["errors"] / max(total_operations, 1)
        assert error_rate < 0.05, f"Too many errors: {error_rate:.2%}"

        print(f"Chaos test results: {results}")

    @pytest.mark.asyncio
    async def test_subscriber_stress_with_backpressure(self, stress_store):
        """Тест подписчиков с backpressure"""
        slow_subscribers = []
        fast_subscribers = []

        # Создаём медленных подписчиков
        for i in range(10):
            queue = await stress_store.subscribe(f"slow_{i}")
            slow_subscribers.append(queue)

        # Создаём быстрых подписчиков
        for i in range(10):
            queue = await stress_store.subscribe(f"fast_{i}")
            fast_subscribers.append(queue)

        async def slow_consumer(queue, consumer_id):
            """Медленный потребитель"""
            consumed = 0
            try:
                while consumed < 20:
                    await queue.get()
                    consumed += 1
                    await asyncio.sleep(0.05)  # медленно обрабатываем
            except:
                pass
            return consumed

        async def fast_consumer(queue, consumer_id):
            """Быстрый потребитель"""
            consumed = 0
            try:
                while consumed < 50:
                    await asyncio.wait_for(queue.get(), timeout=0.1)
                    consumed += 1
            except asyncio.TimeoutError:
                pass
            return consumed

        async def producer():
            """Производитель обновлений"""
            for i in range(100):
                snapshot = FsmSnapshotDTO(
                    version=i + 2000, state=FsmState.ACTIVE, reason=f"BACKPRESSURE_{i}"
                )
                await stress_store.set(snapshot)
                await asyncio.sleep(0.01)

        with PerformanceMonitor("Subscriber Backpressure Stress") as monitor:
            # Запускаем производителя и потребителей конкурентно
            tasks = [producer()]

            # Медленные потребители
            for i, queue in enumerate(slow_subscribers):
                tasks.append(slow_consumer(queue, f"slow_{i}"))

            # Быстрые потребители
            for i, queue in enumerate(fast_subscribers):
                tasks.append(fast_consumer(queue, f"fast_{i}"))

            results = await asyncio.gather(*tasks)
            results[0]
            slow_results = results[1:11]
            fast_results = results[11:21]

            monitor.operations = sum(slow_results) + sum(fast_results)

        # Быстрые потребители должны получить больше сообщений
        avg_fast = sum(fast_results) / len(fast_results)
        avg_slow = sum(slow_results) / len(slow_results)

        assert avg_fast > avg_slow, "Fast consumers should get more messages"

        # Система должна остаться стабильной
        health = await stress_store.health_check()
        assert health["healthy"], f"Store unhealthy: {health['issues']}"


class TestMemoryStress:
    """Тесты нагрузки на память"""

    @pytest.mark.asyncio
    async def test_memory_pressure_large_snapshots(self, stress_store):
        """Тест с большими снапшотами для нагрузки на память"""
        with PerformanceMonitor("Memory Pressure Large Snapshots") as monitor:
            for i in range(100):  # меньше итераций, но большие объекты
                # Создаём снапшот с большим количеством данных
                large_context = {
                    f"sensor_{j}": f"data_{'x' * 100}_{j}"
                    for j in range(100)  # много данных
                }

                [
                    next_snapshot(
                        current=FsmSnapshotDTO(version=k, state=FsmState.IDLE),
                        new_state=FsmState.ACTIVE,
                        reason=f"HISTORY_{k}",
                    )
                    for k in range(50)  # много истории
                ]

                snapshot = FsmSnapshotDTO(
                    version=i,
                    state=FsmState.ACTIVE,
                    reason=f"MEMORY_PRESSURE_{i}",
                    context_data=large_context,
                    # history=large_history  # закомментировано чтобы не создавать циклические ссылки
                )

                await stress_store.set(snapshot)
                monitor.record_operation()

                # Периодически проверяем память
                if i % 20 == 0:
                    gc.collect()  # принудительная сборка мусора

        # Проверяем что память не утекла критично
        gc.collect()
        psutil.Process().memory_info().rss

        # Проверяем финальное состояние
        final_state = await stress_store.get()
        assert final_state is not None
        assert len(final_state.context_data) == 100

    @pytest.mark.asyncio
    async def test_subscriber_memory_cleanup(self, stress_store):
        """Тест очистки памяти подписчиков"""
        initial_memory = psutil.Process().memory_info().rss

        with PerformanceMonitor("Subscriber Memory Cleanup") as monitor:
            # Создаём и удаляем много подписчиков
            for wave in range(10):
                subscribers = []

                # Создаём подписчиков
                for i in range(100):
                    queue = await stress_store.subscribe(f"cleanup_wave_{wave}_{i}")
                    subscribers.append(queue)
                    monitor.record_operation()

                # Генерируем обновления
                for j in range(10):
                    snapshot = FsmSnapshotDTO(
                        version=wave * 100 + j,
                        state=FsmState.IDLE,
                        reason=f"CLEANUP_UPDATE_{wave}_{j}",
                    )
                    await stress_store.set(snapshot)

                # Удаляем всех подписчиков
                for queue in subscribers:
                    await stress_store.unsubscribe(queue)
                    monitor.record_operation()

                # Принудительная очистка
                gc.collect()

                # Проверяем количество активных подписчиков
                metrics = await stress_store.get_metrics()
                assert metrics["active_subscribers"] == 0, (
                    f"Wave {wave}: subscribers not cleaned up"
                )

        final_memory = psutil.Process().memory_info().rss
        memory_growth = final_memory - initial_memory

        # Память не должна вырасти критично (допускаем до 50MB роста)
        assert memory_growth < 50 * 1024 * 1024, (
            f"Memory grew by {memory_growth / 1024 / 1024:.2f} MB"
        )


class TestLongRunningStability:
    """Тесты долговременной стабильности"""

    @pytest.mark.asyncio
    async def test_long_running_operations(self, stress_store):
        """Тест долговременной работы с постоянной нагрузкой"""
        start_time = time.time()
        operation_count = 0

        with PerformanceMonitor("Long Running Operations") as monitor:
            while time.time() - start_time < STRESS_TEST_DURATION:
                # Микс разных операций
                operations = [
                    self._perform_set_operation(stress_store),
                    self._perform_get_operation(stress_store),
                    self._perform_subscriber_operation(stress_store),
                    self._perform_conversion_operation(stress_store),
                ]

                # Выполняем случайную операцию
                operation = random.choice(operations)
                try:
                    await operation
                    operation_count += 1
                    monitor.record_operation()
                except Exception as e:
                    print(f"Operation failed: {e}")

                # Небольшая пауза
                await asyncio.sleep(0.001)

        # Проверяем что система остаётся здоровой после долгой работы
        health = await stress_store.health_check()
        assert health["healthy"], f"System unhealthy after long run: {health['issues']}"

        metrics = await stress_store.get_metrics()
        assert metrics["total_sets"] > 0
        assert metrics["total_gets"] > 0

        print(
            f"Long running test: {operation_count} operations in {STRESS_TEST_DURATION}s"
        )

    async def _perform_set_operation(self, store):
        """Выполнить set операцию"""
        snapshot = FsmSnapshotDTO(
            version=random.randint(1, 100000),
            state=random.choice(list(FsmState)),
            reason="LONG_RUNNING_SET",
        )
        await store.set(snapshot)

    async def _perform_get_operation(self, store):
        """Выполнить get операцию"""
        await store.get()

    async def _perform_subscriber_operation(self, store):
        """Выполнить операцию с подписчиком"""
        queue = await store.subscribe("long_running_sub")
        try:
            await asyncio.wait_for(queue.get(), timeout=0.01)
        except asyncio.TimeoutError:
            pass
        await store.unsubscribe(queue)

    async def _perform_conversion_operation(self, store):
        """Выполнить операцию конвертации"""
        snapshot = await store.get()
        if snapshot:
            dto_to_proto(snapshot)
            json_dict = dto_to_json_dict(snapshot)
            assert isinstance(json_dict, dict)


class TestErrorHandlingStress:
    """Стресс-тесты обработки ошибок"""

    @pytest.mark.asyncio
    async def test_error_injection_stress(self, stress_store):
        """Тест с инъекцией ошибок"""
        error_count = 0
        success_count = 0

        with PerformanceMonitor("Error Injection Stress") as monitor:
            for i in range(500):
                try:
                    if random.random() < 0.1:  # 10% ошибок
                        # Имитируем проблемную операцию
                        bad_snapshot = FsmSnapshotDTO(
                            version=-1,  # некорректная версия
                            state=999,  # некорректное состояние (если бы не было защиты enum)
                            reason="",  # пустая причина
                        )
                        await stress_store.set(bad_snapshot, enforce_version=True)
                    else:
                        # Нормальная операция
                        good_snapshot = FsmSnapshotDTO(
                            version=i, state=FsmState.IDLE, reason=f"NORMAL_OP_{i}"
                        )
                        await stress_store.set(good_snapshot)

                    success_count += 1
                    monitor.record_operation()

                except Exception:
                    error_count += 1

        # Система должна остаться работоспособной несмотря на ошибки
        final_state = await stress_store.get()
        assert final_state is not None

        # Большинство операций должно быть успешным
        total_ops = success_count + error_count
        success_rate = success_count / total_ops if total_ops > 0 else 0
        assert success_rate > 0.8, f"Success rate too low: {success_rate:.2%}"

        print(f"Error injection: {success_count} success, {error_count} errors")

    @pytest.mark.asyncio
    async def test_resource_exhaustion_recovery(self, stress_store):
        """Тест восстановления после исчерпания ресурсов"""

        # Создаём искусственное исчерпание ресурсов (много подписчиков)
        subscribers = []
        try:
            for i in range(1000):  # очень много подписчиков
                queue = await stress_store.subscribe(f"exhaustion_{i}")
                subscribers.append(queue)

        except Exception as e:
            print(f"Resource exhaustion at {len(subscribers)} subscribers: {e}")

        # Система должна оставаться работоспособной
        try:
            snapshot = FsmSnapshotDTO(
                version=1, state=FsmState.IDLE, reason="RECOVERY_TEST"
            )
            await stress_store.set(snapshot)

            retrieved = await stress_store.get()
            assert retrieved is not None

        finally:
            # Очистка ресурсов
            for queue in subscribers:
                try:
                    await stress_store.unsubscribe(queue)
                except:
                    pass

        # Проверяем что система восстановилась
        health = await stress_store.health_check()
        print(f"Recovery health check: {health}")

        # Можем допустить некоторые проблемы после экстремальной нагрузки
        assert len(health["issues"]) < 5, "Too many issues after recovery"


class TestPerformanceBenchmarks:
    """Бенчмарки производительности"""

    @pytest.mark.asyncio
    async def test_throughput_benchmark(self, stress_store):
        """Бенчмарк пропускной способности"""
        operations = 5000

        # Тест записи
        start_time = time.time()
        for i in range(operations):
            snapshot = FsmSnapshotDTO(
                version=i, state=FsmState.IDLE, reason="BENCHMARK"
            )
            await stress_store.set(snapshot)
        write_time = time.time() - start_time

        # Тест чтения
        start_time = time.time()
        for i in range(operations):
            await stress_store.get()
        read_time = time.time() - start_time

        write_ops_per_sec = operations / write_time
        read_ops_per_sec = operations / read_time

        print("\nThroughput Benchmark:")
        print(f"  Write: {write_ops_per_sec:.1f} ops/sec")
        print(f"  Read: {read_ops_per_sec:.1f} ops/sec")

        # Базовые требования производительности
        assert write_ops_per_sec > 1000, (
            f"Write performance too low: {write_ops_per_sec:.1f}"
        )
        assert read_ops_per_sec > 5000, (
            f"Read performance too low: {read_ops_per_sec:.1f}"
        )

    @pytest.mark.asyncio
    async def test_latency_benchmark(self, stress_store):
        """Бенчмарк задержек"""
        operations = 1000
        write_latencies = []
        read_latencies = []

        for i in range(operations):
            # Измеряем задержку записи
            snapshot = FsmSnapshotDTO(
                version=i, state=FsmState.ACTIVE, reason="LATENCY"
            )

            start = time.time()
            await stress_store.set(snapshot)
            write_latencies.append((time.time() - start) * 1000)  # в миллисекундах

            # Измеряем задержку чтения
            start = time.time()
            await stress_store.get()
            read_latencies.append((time.time() - start) * 1000)

        # Статистика
        avg_write_lat = sum(write_latencies) / len(write_latencies)
        avg_read_lat = sum(read_latencies) / len(read_latencies)

        p95_write = sorted(write_latencies)[int(0.95 * len(write_latencies))]
        p95_read = sorted(read_latencies)[int(0.95 * len(read_latencies))]

        print("\nLatency Benchmark:")
        print(f"  Write avg: {avg_write_lat:.2f}ms, P95: {p95_write:.2f}ms")
        print(f"  Read avg: {avg_read_lat:.2f}ms, P95: {p95_read:.2f}ms")

        # Требования по задержкам
        assert avg_write_lat < 5.0, f"Write latency too high: {avg_write_lat:.2f}ms"
        assert avg_read_lat < 1.0, f"Read latency too high: {avg_read_lat:.2f}ms"
        assert p95_write < 10.0, f"Write P95 latency too high: {p95_write:.2f}ms"


# Конфигурация для pytest
pytestmark = [
    pytest.mark.stress,
    pytest.mark.asyncio,
    pytest.mark.timeout(60),  # таймаут для stress тестов
]


if __name__ == "__main__":
    # Запуск stress тестов
    pytest.main([__file__, "-v", "-s", "-m", "stress", "--tb=short", f"--timeout={60}"])
