# TEST_STRESS.PY — аналитический отчёт

## Вход и цель
- [Факт] Анализ модуля `test_stress.py`.
- [Факт] Итог — обзор стресс-тестов StateStore.

## Сбор контекста
- [Факт] Прочитан исходник `test_stress.py` и связанные `store.py`, `types.py`.
- [Гипотеза] Тесты запускаются из CI для оценки устойчивости.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/state/tests/test_stress.py`.
- [Факт] Требуются `pytest`, `psutil`, `asyncio`.

## Фактический разбор
- [Факт] Фикстура `stress_store` создаёт инициализированный `AsyncStateStore`.
- [Факт] Класс `PerformanceMonitor` измеряет время операций.
- [Факт] Группы тестов: `TestHighVolumeOperations`, `TestConcurrencyStress`, `TestMemoryStress`, `TestLongRunningStability`, `TestPerformanceBenchmarks`.
- [Факт] Проверяются массовые `set/get`, конкурентные писатели и подписчики, утечки памяти.

## Роль в системе и связи
- [Факт] Тесты валидируют StateStore под экстремальными нагрузками.
- [Гипотеза] Результаты используются для настройки порогов производительности.

## Несоответствия и риски
- [Факт] Значения `HIGH_LOAD_OPERATIONS=1000`, `CONCURRENCY_WORKERS=50` могут быть малы для реального продакшена.
- [Гипотеза] Отсутствует контроль за временем GC, что может повлиять на измерения.

## Мини-патчи (safe-fix)
- [Патч] Параметризовать пороговые значения через переменные окружения.
- [Патч] Добавить явный вызов `gc.collect()` перед измерениями.

## Рефактор-скетч
```python
def run_with_monitor(name, coro):
    mon = PerformanceMonitor(name)
    mon.start()
    asyncio.run(coro())
    mon.stop()
    assert mon.elapsed < 1.0
```

## Примеры использования
- [Факт]
```bash
pytest services/q_core_agent/state/tests/test_stress.py::TestHighVolumeOperations::test_high_volume_sets_and_gets -q
```
- [Факт]
```bash
pytest services/q_core_agent/state/tests/test_stress.py::TestConcurrencyStress::test_concurrent_writers_stress -q
```

## Тест-хуки/чек-лист
- [Факт] Проверить лимиты CPU/RAM перед запуском.
- [Факт] Анализировать отчёт `PerformanceMonitor` на наличие пиков.

## Вывод
- [Факт] Модуль покрывает критичные сценарии нагрузки.
- [Гипотеза] Для длительных тестов стоит вынести их в отдельный профилирующий пакет.
