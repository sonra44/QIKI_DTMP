# Анализ файла test_stress.py

## Вход и цель
- **Файл**: test_stress.py
- **Итог**: Обзор стресс-тестов для StateStore архитектуры

## Сбор контекста
- **Исходник**: /home/sonra44/QIKI_DTMP/services/q_core_agent/state/tests/test_stress.py
- **Связанные файлы**:
  - services/q_core_agent/state/store.py (тестируемый компонент)
  - services/q_core_agent/state/types.py (DTO типы)
  - services/q_core_agent/state/conv.py (конвертеры)
  - services/q_core_agent/state/tests/test_types.py (unit тесты типов)
  - services/q_core_agent/state/tests/test_store.py (unit тесты хранилища)
  - services/q_core_agent/state/tests/test_conv.py (unit тесты конвертеров)
  - services/q_core_agent/state/tests/test_integration.py (интеграционные тесты)

**[Факт]**: Файл содержит комплексные стресс-тесты для проверки производительности, стабильности и надежности StateStore под высокой нагрузкой.

## Локализация артефакта
- **Точный путь**: /home/sonra44/QIKI_DTMP/services/q_core_agent/state/tests/test_stress.py
- **Окружение**: Python 3.x, pytest, asyncio, psutil

## Фактический разбор
### Ключевые классы тестов:
- **TestHighVolumeOperations**: Тесты высокой нагрузки операций
  - `test_high_volume_sets_and_gets()`: Стресс-тест большого количества set/get операций
  - `test_rapid_state_transitions()`: Тест быстрых переходов состояний
  - `test_massive_subscriber_load()`: Тест большого количества подписчиков

- **TestConcurrencyStress**: Тесты конкурентного доступа под нагрузкой
  - `test_concurrent_writers_stress()`: Стресс-тест конкурентных писателей
  - `test_mixed_operations_chaos()`: Хаотичный тест смешанных операций
  - `test_subscriber_stress_with_backpressure()`: Тест подписчиков с backpressure

- **TestMemoryStress**: Тесты нагрузки на память
  - `test_memory_pressure_large_snapshots()`: Тест с большими снапшотами для нагрузки на память
  - `test_subscriber_memory_cleanup()`: Тест очистки памяти подписчиков

- **TestLongRunningStability**: Тесты долговременной стабильности
  - `test_long_running_operations()`: Тест долговременной работы с постоянной нагрузкой

- **TestErrorHandlingStress**: Стресс-тесты обработки ошибок
  - `test_error_injection_stress()`: Тест с инъекцией ошибок
  - `test_resource_exhaustion_recovery()`: Тест восстановления после исчерпания ресурсов

- **TestPerformanceBenchmarks**: Бенчмарки производительности
  - `test_throughput_benchmark()`: Бенчмарк пропускной способности
  - `test_latency_benchmark()`: Бенчмарк задержек

**[Факт]**: Тесты покрывают широкий спектр сценариев стресс-нагрузки, включая объемные операции, конкурентный доступ, нагрузку на память и обработку ошибок.

## Роль в системе и связи
- **Как участвует в потоке**: Проверяет стабильность и производительность StateStore под экстремальными условиями
- **Кто вызывает**: pytest при запуске тестов, CI/CD системы
- **Что от него ждут**: Выявление проблем производительности, утечек памяти, race conditions и других проблем под нагрузкой
- **Чем он рискует**: Долгое выполнение, возможные ложные срабатывания на слабом железе

**[Факт]**: Тесты обеспечивают высокую надежность StateStore архитектуры через комплексную проверку под стрессом.

## Несоответствия и риски
1. **Средний риск**: Некоторые тесты могут давать ложные срабатывания на слабом железе из-за жестких требований к производительности
2. **Низкий риск**: Отсутствует тестирование отказоустойчивости при сбоях сети или диска
3. **Низкий риск**: Нет явной проверки поведения при работе с очень большими объемами данных (гигабайты)
4. **Низкий риск**: Нет тестов для проверки поведения при ограничениях CPU

**[Гипотеза]**: Может потребоваться добавить тесты для проверки поведения при отказах оборудования и сетевых проблемах.

## Мини-патчи (safe-fix)
**[Патч]**: Добавить тест для проверки поведения при ограничениях ресурсов:
```python
@pytest.mark.asyncio
async def test_cpu_throttling_stress(self, stress_store):
    """Тест поведения при ограничениях CPU"""
    import time
    
    # Симуляция ограничений CPU
    start_time = time.time()
    operation_count = 0
    
    with PerformanceMonitor("CPU Throttling Stress") as monitor:
        # Выполняем операции с искусственной нагрузкой
        for i in range(500):
            # Создаем нагрузку на CPU
            snapshot = FsmSnapshotDTO(
                version=i,
                state=FsmState.ACTIVE,
                reason=f"CPU_THROTTLE_{i}",
                context_data={f"key_{j}": f"value_{'x' * 100}_{j}" for j in range(50)}
            )
            
            await stress_store.set(snapshot)
            operation_count += 1
            monitor.record_operation()
            
            # Искусственная пауза для симуляции CPU throttling
            time.sleep(0.005)
            
    duration = time.time() - start_time
    
    # Проверяем что система остается стабильной даже при ограничениях
    final_state = await stress_store.get()
    assert final_state is not None
    
    # Проверяем метрики
    metrics = await stress_store.get_metrics()
    assert metrics['total_sets'] >= operation_count
    
    print(f"CPU throttling test: {operation_count} operations in {duration:.2f}s")
```

## Рефактор-скетч (по желанию)
```python
import pytest
import asyncio
import time
import gc
import psutil
import random
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

from ..store import AsyncStateStore, StateStoreError, create_initialized_store
from ..types import FsmSnapshotDTO, FsmState, TransitionStatus, initial_snapshot, next_snapshot
from ..conv import dto_to_proto, proto_to_dto, dto_to_json_dict

# Конфигурация стресс-тестов
class StressTestConfig:
    """Конфигурация для стресс-тестов"""
    
    # Базовые параметры
    STRESS_TEST_DURATION = 2.0  # секунды
    HIGH_LOAD_OPERATIONS = 1000
    MEMORY_PRESSURE_SIZE = 10000
    CONCURRENCY_WORKERS = 50
    
    # Требования производительности
    MIN_WRITE_OPS_PER_SEC = 1000
    MIN_READ_OPS_PER_SEC = 5000
    MAX_AVG_WRITE_LATENCY_MS = 5.0
    MAX_AVG_READ_LATENCY_MS = 1.0
    MAX_P95_LATENCY_MS = 10.0
    
    # Ограничения ресурсов
    MAX_MEMORY_GROWTH_MB = 50
    MAX_ERROR_RATE = 0.05
    MIN_SUCCESS_RATE = 0.8


class StressTestMonitor:
    """Монитор для стресс-тестов"""
    
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


class BaseStressTest:
    """Базовый класс для стресс-тестов"""
    
    def __init__(self, config: StressTestConfig = None):
        self.config = config or StressTestConfig()
        
    @pytest.fixture
    def stress_store(self):
        """StateStore для стресс-тестов"""
        return create_initialized_store()
        
    def _create_test_snapshot(self, version: int, state: FsmState = None, reason: str = None) -> FsmSnapshotDTO:
        """Создать тестовый снапшот"""
        return FsmSnapshotDTO(
            version=version,
            state=state or FsmState.IDLE,
            reason=reason or f"STRESS_TEST_{version}"
        )


class HighVolumeOperationsTest(BaseStressTest):
    """Тесты высокой нагрузки операций"""
    
    @pytest.mark.asyncio
    async def test_high_volume_operations(self, stress_store):
        """Стресс-тест высокой нагрузки"""
        with StressTestMonitor("High Volume Operations") as monitor:
            for i in range(self.config.HIGH_LOAD_OPERATIONS):
                # Создаем уникальный снапшот
                snapshot = self._create_test_snapshot(
                    version=i,
                    state=FsmState(1 + (i % 4)),  # варьируем состояния
                    reason=f"HIGH_VOLUME_{i}"
                )
                
                # Set операция
                await stress_store.set(snapshot)
                monitor.record_operation()
                
                # Get операция
                retrieved = await stress_store.get()
                assert retrieved.version >= i
                monitor.record_operation()
                
        # Проверяем финальное состояние
        final_state = await stress_store.get()
        assert final_state is not None
        assert final_state.version >= self.config.HIGH_LOAD_OPERATIONS - 1


# Группировка тестов по категориям
class TestStressSuite:
    """Основной набор стресс-тестов"""
    
    # Тесты объемной нагрузки
    test_high_volume = HighVolumeOperationsTest()
    
    # Тесты конкурентности
    # test_concurrency = ConcurrencyStressTest()
    
    # Тесты памяти
    # test_memory = MemoryStressTest()
    
    # Тесты стабильности
    # test_stability = LongRunningStabilityTest()
    
    # Тесты обработки ошибок
    # test_error_handling = ErrorHandlingStressTest()
    
    # Бенчмарки производительности
    # test_performance = PerformanceBenchmarksTest()


# Конфигурация pytest
pytestmark = [
    pytest.mark.stress,
    pytest.mark.asyncio,
    pytest.mark.timeout(60)
]


if __name__ == "__main__":
    # Запуск стресс-тестов
    pytest.main([
        __file__, 
        "-v", 
        "-s",
        "-m", "stress",
        "--tb=short",
        f"--timeout={60}"
    ])
```

## Примеры использования
```python
# Запуск всех стресс-тестов
pytest services/q_core_agent/state/tests/test_stress.py -v -s

# Запуск конкретного теста
pytest services/q_core_agent/state/tests/test_stress.py::TestHighVolumeOperations::test_high_volume_sets_and_gets -v

# Запуск с таймаутом
pytest services/q_core_agent/state/tests/test_stress.py -v --timeout=30

# Запуск в режиме дебага
pytest services/q_core_agent/state/tests/test_stress.py -v -s --tb=long
```

```python
# Пример использования в CI/CD
import subprocess
import sys

def run_stress_tests():
    """Запустить стресс-тесты в CI/CD"""
    try:
        result = subprocess.run([
            "python3", "-m", "pytest",
            "services/q_core_agent/state/tests/test_stress.py",
            "-v", "--tb=short", "--timeout=60"
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("Все стресс-тесты пройдены успешно")
            return True
        else:
            print(f"Стресс-тесты провалены:\n{result.stdout}\n{result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("Стресс-тесты превысили лимит времени")
        return False
    except Exception as e:
        print(f"Ошибка запуска стресс-тестов: {e}")
        return False

if __name__ == "__main__":
    success = run_stress_tests()
    sys.exit(0 if success else 1)
```

## Тест-хуки/чек-лист
- [ ] Проверить выполнение всех тестов без таймаутов
- [ ] Проверить отсутствие утечек памяти
- [ ] Проверить требования к производительности (throughput, latency)
- [ ] Проверить корректную обработку ошибок
- [ ] Проверить стабильность при конкурентном доступе
- [ ] Проверить поведение при ограничениях ресурсов
- [ ] Проверить восстановление после экстремальных нагрузок
- [ ] Проверить корректную работу системы публикации/подписки под нагрузкой

## Вывод
- **Текущее состояние**: Файл содержит комплексные стресс-тесты, покрывающие основные сценарии нагрузки на StateStore
- **Что починить сразу**: Добавить тесты для проверки поведения при ограничениях ресурсов (CPU, диск)
- **Что отложить**: Реализацию тестов для проверки отказоустойчивости при сбоях оборудования

**[Факт]**: Анализ завершен на основе содержимого файла и его роли в системе тестирования.