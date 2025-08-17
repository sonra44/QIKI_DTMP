# TEST_INTEGRATION.PY — аналитический отчёт

## Вход и цель
- [Факт] Анализ модуля `test_integration.py`.
- [Факт] Итог — обзор интеграционных сценариев FSMHandler + StateStore.

## Сбор контекста
- [Факт] Изучен исходник теста и модули `store.py`, `types.py`, `conv.py`.
- [Гипотеза] Тесты служат для проверки цепочки DTO → FSM → Store.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/state/tests/test_integration.py`.
- [Факт] Зависят от `pytest`, `asyncio`.

## Фактический разбор
- [Факт] Используются фикстуры `mock_context`, `state_store`, `fsm_handler`.
- [Факт] Тесты проверяют переходы `BOOTING→IDLE→ACTIVE→IDLE→ERROR_STATE`.
- [Факт] Убедятся в монотонности версий и отсутствии изменений без условий.

## Роль в системе и связи
- [Факт] Проверяет взаимодействие FSMHandler и StateStore на реальных сценариях.
- [Гипотеза] Используется при разработке логики управления состоянием агента.

## Несоответствия и риски
- [Факт] В тестах отсутствует проверка логирования ошибок FSMHandler.
- [Гипотеза] Возможен дрейф поведения при расширении контекста агента.

## Мини-патчи (safe-fix)
- [Патч] Добавить проверки на корректное логирование при ошибочных переходах.
- [Патч] Параметризовать последовательности переходов для новых сценариев.

## Рефактор-скетч
```python
async def process_and_assert(handler, dto, expected_state):
    res = await handler.process_fsm_dto(dto)
    assert res.state == expected_state
    return res
```

## Примеры использования
- [Факт]
```bash
pytest services/q_core_agent/state/tests/test_integration.py::TestFSMHandlerStateStoreIntegration::test_basic_fsm_processing_with_store -q
```
- [Факт]
```bash
pytest services/q_core_agent/state/tests/test_integration.py::TestFSMHandlerStateStoreIntegration::test_version_monotonicity -q
```

## Тест-хуки/чек-лист
- [Факт] Симулировать отказ BIOS и проверять состояние `ERROR_STATE`.
- [Факт] Проверять сохранение DTO в Store после каждого перехода.

## Вывод
- [Факт] Модуль покрывает базовые цепочки взаимодействия FSMHandler и StateStore.
- [Гипотеза] Для полноты стоит добавить тесты с конкурирующими событиями.
