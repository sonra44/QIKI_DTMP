СПИСОК ФАЙЛОВ

# Вход и цель
- [Факт] Файл `services/q_core_agent/state/tests/test_store.py` — unit и concurrency тесты для `AsyncStateStore`.
- [Факт] Итог: анализ проверок стора, подписчиков, метрик и ошибок.

# Сбор контекста
- [Факт] Использует `pytest`, `asyncio`, `uuid`, `ThreadPoolExecutor`.
- [Факт] Тестирует `AsyncStateStore`, `StateStoreError`, `StateVersionError`, а также вспомогательные функции `create_store`, `create_initialized_store`.
- [Гипотеза] Основной набор тестов для гарантии корректности StateStore.

# Локализация артефакта
- [Факт] Путь: `services/q_core_agent/state/tests/test_store.py`.
- [Факт] Запуск: `python3 -m pytest services/q_core_agent/state/tests/test_store.py`.
- [Гипотеза] Требует асинхронного event loop и достаточного таймаута.

# Фактический разбор
## Фикстуры
- [Факт] `empty_store` — новый `AsyncStateStore` без состояния.
- [Факт] `initialized_store` — стор с `initial_snapshot`.
- [Факт] `sample_snapshot` — DTO для базовых операций.
## Тестовые блоки
- [Факт] `TestAsyncStateStoreBasics` — get/set, автоинкремент версий, immutability, get_with_meta.
- [Факт] `TestAsyncStateStorePubSub` — подписка, отписка, переполнение очереди, очистка мёртвых подписчиков.
- [Факт] `TestAsyncStateStoreConcurrency` — конкурентные get/set/subscribe.
- [Факт] `TestAsyncStateStoreMetrics` — метрики total_sets, total_gets, conflicts, health_check.
- [Факт] `TestAsyncStateStoreHelpers` — create_store, initialize_if_empty.
- [Факт] `TestAsyncStateStoreErrorHandling` — обработка плохих DTO и ошибок подписчиков.
## Граничные случаи
- [Факт] Проверяется версия при enforce_version=True.
- [Гипотеза] Очистка подписчиков через `_lock` может замедлить высокую конкуренцию.

# Роль в системе и связи
- [Факт] Гарантирует корректность базовых операций StateStore, на которые опираются интеграционные и стресс‑тесты.
- [Гипотеза] Является основой для дальнейших модулей агента.

# Несоответствия и риски
- [Гипотеза] Тест `dead_subscriber_cleanup` опирается на приватный атрибут `_closed` (Low).
- [Гипотеза] Конкурентные тесты используют фиксированные задержки `sleep`, что может быть нестабильно (Med).

# Мини‑патчи (safe-fix)
- [Патч] Ввести публичный метод `mark_closed` для подписчиков в тестах.
- [Патч] Заменить `sleep` на ожидание событий при concurrency тестах.

# Рефактор‑скетч
```python
async def set_snapshot(store, dto):
    async with store._lock:
        if dto is None: raise StateStoreError
        return await store._set_internal(dto)
```

# Примеры использования
```bash
# 1. Запуск всех тестов стора
python3 -m pytest services/q_core_agent/state/tests/test_store.py -v
# 2. Только pub/sub
python3 -m pytest services/q_core_agent/state/tests/test_store.py -k pubsub -v
# 3. Проверка метрик
python3 -m pytest services/q_core_agent/state/tests/test_store.py -k metrics -v
# 4. Запуск конкурентных операций
python3 -m pytest services/q_core_agent/state/tests/test_store.py -k concurrency -v
# 5. Быстрый запуск с выводом
python3 -m pytest services/q_core_agent/state/tests/test_store.py -q
```

# Тест‑хуки/чек‑лист
- [Факт] Проверить, что `initialize_if_empty` создаёт `BOOTING` снапшот.
- [Факт] Убедиться, что переполненные очереди не вызывают исключений.
- [Факт] Метрика `version_conflicts` увеличивается при enforce_version ошибках.
- [Факт] `health_check()` сообщает о накопленных конфликтах.
- [Факт] Конкурентные set операции не вызывают ошибок и повышают версию.

# Вывод
1. [Факт] Тесты покрывают функциональность, pub/sub, конкуренцию и метрики StateStore.
2. [Факт] Проверяются ошибки версий и некорректные данные.
3. [Гипотеза] Задержки `sleep` могут привести к нестабильности.
4. [Факт] Есть проверки очистки подписчиков и метрик здоровья.
5. [Патч] Использовать события вместо `sleep` в конкурентных тестах.
6. [Гипотеза] Стоит добавить тест на сохранение порядка подписчиков.
7. [Патч] Создать API для искусственного закрытия очередей в тестах.
8. [Гипотеза] Метрики можно экспонировать через Prometheus.
9. [Патч] Проверять обработку больших `context_data` в store.
10. [Гипотеза] Интегрировать результаты в общий отчёт `hot_test_statestore.sh`.

СПИСОК ФАЙЛОВ
