# Отчет: `services/q_core_agent/core/ship_fsm_handler.py`

## Вход и цель
- [Факт] Проанализировать обработчик конечного автомата корабля для фиксации функций и рисков.

## Сбор контекста
- [Факт] Изучен исходник `ship_fsm_handler.py`.
- [Факт] Сопоставлены зависимости: `IFSMHandler`, `ShipCore`, `ShipActuatorController`.
- [Гипотеза] Используется вместе с protobuf-сообщениями `FSMState` и `StateTransition`.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/ship_fsm_handler.py`.
- [Факт] Запускается внутри агента QIKI, требует импортов из `generated/`.

## Фактический разбор
- [Факт] Enum `ShipState` описывает 10 состояний (STARTUP, IDLE, FLIGHT*, DOCKING*, EMERGENCY*).
- [Факт] Класс `ShipContext` агрегирует проверки систем, навигации и стыковки.
- [Факт] Основной класс `ShipFSMHandler` реализует `process_fsm_state` с логикой переходов и `_execute_emergency_stop`.
- [Факт] Логирует переходы и формирует `StateTransition`.

## Роль в системе и связи
- [Факт] Зависит от `ShipCore` для статусов и `ShipActuatorController` для команд.
- [Гипотеза] Результаты передаются в вышестоящий планировщик полета.

## Несоответствия и риски
- [Факт] `is_docking_target_in_range` всегда возвращает False → неполная реализация (Low).
- [Факт] Отсутствует таймаут или лимит истории переходов (Med).
- [Гипотеза] Логирование через `print` в mock-среде может засорять вывод (Low).

## Мини-патчи (safe-fix)
- [Патч] Добавить заглушку TODO в `is_docking_target_in_range` с описанием ожидаемых данных.
- [Патч] Ограничить размер `history` в `FSMState` для контроля памяти.

## Рефактор-скетч
```python
if docking_target is None:
    logger.debug("No docking target")
```

## Примеры использования
```python
ship = ShipCore(base_path="./")
controller = ShipActuatorController(ship)
fsm = ShipFSMHandler(ship, controller)
next_state = fsm.process_fsm_state(FSMState())
```

## Тест-хуки/чек-лист
- [Факт] Проверить переход STARTUP→IDLE при `systems_ok=True`.
- [Факт] Проверить аварийную остановку из FLIGHT при `systems_ok=False`.

## Вывод
- [Факт] FSM покрывает основные режимы корабля, но некоторые функции неполны.
- [Гипотеза] Нужна доработка логики стыковки и контроля истории.
- [Патч] Ограничить историю и документировать необходимые сенсоры для стыковки.
