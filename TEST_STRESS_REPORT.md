# services/q_core_agent/state/tests/test_stress.py — анализ по методу «Задачи»

## Назначение файла
Набор расширенных stress‑ и concurrency‑тестов для проверки StateStore под высокой нагрузкой и длительной работой.

## Основные блоки задач
### 1. `TestHighVolumeOperations`
- [ ] `test_high_volume_sets_and_gets` — множество операций `set/get` с мониторингом производительности.
- [ ] `test_rapid_state_transitions` — быстрые смены состояний и проверка метрик.
- [ ] `test_massive_subscriber_load` — сотни подписчиков и проверка доставки обновлений.

### 2. `TestConcurrencyStress`
- [ ] `test_concurrent_writers_stress` — десятки конкурентных писателей.
- [ ] `test_mixed_operations_chaos` — смесь чтений, записей и подписок.
- [ ] `test_subscriber_stress_with_backpressure` — сравнение быстрых и медленных потребителей.

### 3. `TestMemoryStress`
- [ ] `test_memory_pressure_large_snapshots` — большие объекты и контроль памяти.
- [ ] `test_subscriber_memory_cleanup` — массовое создание/удаление подписчиков.

### 4. `TestLongRunningStability`
- [ ] `test_long_running_operations` — непрерывные случайные операции на протяжении `STRESS_TEST_DURATION`.
- [ ] `test_resource_exhaustion_recovery` — восстановление после исчерпания ресурсов.

### 5. `TestPerformanceBenchmarks`
- [ ] `test_throughput_benchmark` — измерение пропускной способности `set/get`.
- [ ] `test_latency_benchmark` — измерение задержек с вычислением P95.

## Наблюдения и рекомендации
- Тесты используют `PerformanceMonitor` для единообразной статистики.
- Значения нагрузок и таймаутов уменьшены для CI, но могут масштабироваться.
- Для успешного запуска требуется плагин `pytest-asyncio` и библиотека `psutil`.
