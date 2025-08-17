# Отчёт по файлу `services/q_core_agent/core/fsm_handler.py`

 codex/analyze-files-and-create-md-reports-rngq70
## Вход и цель
- [Факт] Реализация `FSMHandler` для вычисления переходов и записи в StateStore; цель — управлять состоянием конечного автомата агента.

## Сбор контекста
- [Факт] Импортирует `FsmSnapshotDTO`, `TransitionDTO`, `FsmState`, `TransitionStatus`, `create_transition`, `next_snapshot`, `dto_to_proto` и legacy protobuf типы.
- [Гипотеза] `AgentContext` предоставляет методы `is_bios_ok` и `has_valid_proposals`.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/fsm_handler.py`.

## Фактический разбор
- [Факт] `FSMHandler` инициализируется контекстом и опциональным `AsyncStateStore`.
- [Факт] `process_fsm_dto` вычисляет новое состояние, создаёт `TransitionDTO` при изменении и сохраняет снапшот в `state_store`.
- [Факт] `_compute_transition_dto` содержит правила переходов между `BOOTING`, `IDLE`, `ACTIVE`, `ERROR_STATE`.
- [Факт] `process_fsm_state` реализует legacy-обработку на `FsmStateSnapshot`.

## Роль в системе и связи
- [Факт] Единственная точка записи состояния FSM в `StateStore`.
- [Гипотеза] Используется `TickOrchestrator` через `agent.fsm_handler`.

## Несоответствия и риски
- [Гипотеза] При исключении `state_store.set` отсутствует повторная попытка записи (Med).
- [Гипотеза] Логика переходов в DTO и legacy-методе может рассинхронизироваться (Low).

## Мини-патчи (safe-fix)
- [Патч] Обернуть `state_store.set` в retry и логировать детали ошибки.
- [Патч] Выделить общую таблицу переходов, используемую в DTO и legacy коде.

## Рефактор-скетч (по желанию)
```python
# [Патч] Таблица переходов
TRANSITIONS = {
    FsmState.BOOTING: {True: (FsmState.IDLE, "BOOT_COMPLETE"), False: (FsmState.ERROR_STATE, "BIOS_ERROR")},
    # ...
}
```

## Примеры использования
- [Факт] `await fsm_handler.process_fsm_dto(snapshot)` — обработка DTO.
- [Факт] `fsm_handler.process_fsm_state(proto_snapshot)` — legacy путь.

## Тест-хуки/чек-лист
- [Факт] Мок `state_store.set` для проверки записи и обработки ошибок.
- [Факт] Проверка переходов при разных значениях `bios_ok` и `has_proposals`.

## Вывод
- [Факт] Handler покрывает новую DTO-архитектуру и legacy-протобуф.
- [Патч] Требуются улучшения обработки ошибок и унификация переходов.

## Стиль и маркировка
Использованы теги [Факт], [Гипотеза], [Патч] для обозначения уровня уверенности.
=======
## Задачи
- Управление логикой конечного автомата агента на уровне DTO и взаимодействие с `AsyncStateStore`.
- Вычисление переходов на основе статуса BIOS и наличия предложений, формирование `TransitionDTO`.
- Создание нового снапшота через `next_snapshot` и запись состояния в хранилище.
- Предоставление легаси-метода на protobuf для совместимости.
 main
