СПИСОК ФАЙЛОВ

# Вход и цель
- [Факт] Файл `services/q_core_agent/state/tests/test_integration.py` — интеграционные тесты FSMHandler + StateStore.
- [Факт] Итог: обзор сценариев интеграции и потенциальных улучшений.

# Сбор контекста
- [Факт] Использует `pytest`, `AsyncMock`, `patch`, классы `AsyncStateStore`, `FsmSnapshotDTO`, `MockFSMHandler`.
- [Факт] Рядом находятся модули `store.py`, `types.py`, `conv.py`.
- [Гипотеза] Файл имитирует поведение агента без зависимости от остального core.

# Локализация артефакта
- [Факт] Путь: `services/q_core_agent/state/tests/test_integration.py`.
- [Факт] Запуск через `python3 -m pytest services/q_core_agent/state/tests/test_integration.py`.
- [Гипотеза] Требует установленных protobuf и окружения StateStore.

# Фактический разбор
## Фикстуры и моки
- [Факт] `MockAgentContext` моделирует контекст с полями BIOS, proposals.
- [Факт] `MockFSMHandler` выполняет упрощённые переходы FSM и сохраняет их в `AsyncStateStore`.
- [Факт] Фикстуры `mock_context`, `state_store`, `fsm_handler` подготавливают окружение.
## Тестовые блоки
- [Факт] `TestFSMHandlerStateStoreIntegration` — проверка последовательных переходов и монотонности версий.
- [Факт] `TestStateStoreSubscriberIntegration` — подписчики получают обновления от FSM.
- [Факт] `TestConversionIntegration` — roundtrip конвертации DTO ↔ protobuf/JSON.
- [Факт] `TestConcurrentIntegration` — конкурентная обработка FSM и подписчиков.
- [Факт] `TestFeatureFlagIntegration` — проверка переменной `QIKI_USE_STATESTORE` и graceful degradation.
## Поведение и граничные случаи
- [Факт] Многие тесты используют `asyncio.wait_for` для контроля времени.
- [Гипотеза] Длинные строки/большие context_data могут вызвать ошибки конвертации.

# Роль в системе и связи
- [Факт] Проверяет связку FSMHandler ↔ StateStore и взаимодействие подписчиков.
- [Гипотеза] Служит основой для проверки поведения агента без запуска всей системы.

# Несоответствия и риски
- [Гипотеза] Использование внутренних полей `state_store._subscribers` в тестах нарушает инкапсуляцию (Med).
- [Гипотеза] Тесты зависят от времени (`asyncio.sleep`), что может быть нестабильно (Low).

# Мини‑патчи (safe-fix)
- [Патч] Добавить helper‑методы для прямой работы с подписчиками вместо обращения к `_subscribers`.
- [Патч] Сократить использование `sleep`, заменить на события/сигналы.

# Рефактор‑скетч
```python
class MockFSMHandler:
    async def process_fsm_dto(self, current):
        new_state = ...
        snap = next_snapshot(current, new_state, reason)
        return await self.state_store.set(snap) if self.state_store else snap
```

# Примеры использования
```bash
# 1. Запуск всех интеграционных тестов
python3 -m pytest services/q_core_agent/state/tests/test_integration.py -v
# 2. Только подписчики
python3 -m pytest services/q_core_agent/state/tests/test_integration.py -k subscriber -v
# 3. Проверка feature флагов
python3 -m pytest services/q_core_agent/state/tests/test_integration.py -k feature_flag -v
# 4. Запуск с выводом stdout
python3 -m pytest services/q_core_agent/state/tests/test_integration.py -s
# 5. Параллельные переходы
python3 -m pytest services/q_core_agent/state/tests/test_integration.py -k concurrent_fsm -v
```

# Тест‑хуки/чек‑лист
- [Факт] Проверить, что версии снапшотов растут монотонно.
- [Факт] Убедиться, что `subscribe` возвращает начальное состояние.
- [Факт] Конвертация DTO ↔ protobuf ↔ JSON сохраняет поля.
- [Факт] При отключённом StateStore FSMHandler всё ещё работает.
- [Факт] Ошибки подписчиков не влияют на остальных.

# Вывод
1. [Факт] Тесты покрывают ключевые сценарии интеграции FSMHandler и StateStore.
2. [Факт] Используются моки для изоляции от core‑логики.
3. [Гипотеза] Прямой доступ к приватным структурам может привести к хрупкости тестов.
4. [Факт] Есть проверки подписчиков и конвертаций.
5. [Патч] Ввести публичный API для управления подписчиками в тестах.
6. [Гипотеза] Можно расширить тесты на обработку ошибок сетевого уровня.
7. [Патч] Заменить `sleep` на синхронизацию через события.
8. [Гипотеза] Интеграцию можно включить в общий отчёт hot‑test скрипта.
9. [Патч] Добавить фикстуру для временной директории под отчёты.
10. [Гипотеза] Возможна параметризация тестов по флагам окружения.

СПИСОК ФАЙЛОВ
