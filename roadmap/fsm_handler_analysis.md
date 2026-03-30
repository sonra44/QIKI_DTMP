# СПИСОК ФАЙЛОВ
- services/q_core_agent/core/fsm_handler.py

## Вход и цель
Исследование `FSMHandler`; цель — понять обработку переходов FSM и взаимодействие со StateStore.

## Сбор контекста
- [Факт] Импорты: `IFSMHandler`, `agent_logger`, DTO, protobuf.
- [Факт] Содержит методы `process_fsm_dto`, `_compute_transition_dto`, `process_fsm_state`.
- [Гипотеза] Используется агентом в каждой итерации тика.

## Локализация артефакта
- Путь: `services/q_core_agent/core/fsm_handler.py`
- Окружение: Python; зависит от `AsyncStateStore`.

## Фактический разбор
- [Факт] `process_fsm_dto` вычисляет новые состояния, создаёт переходы, сохраняет в StateStore.
- [Факт] `_compute_transition_dto` определяет следующее состояние на основе BIOS и предложений.
- [Факт] `process_fsm_state` — легаси версия на protobuf.

## Роль в системе и связи
- [Факт] Единственный писатель FSM состояний в StateStore.
- [Гипотеза] От него зависит корректность логики переходов агента.

## Несоответствия и риски
- [Гипотеза][Med] Дублирование логики между DTO и protobuf версиями.
- [Гипотеза][Low] Нет явной обработки ошибок StateStore в `process_fsm_dto` (падает в лог и продолжает).

## Мини-патчи (safe-fix)
- [Патч] Вынести таблицу переходов в конфиг.
- [Патч] Добавить типизацию возврата для `_compute_transition_dto` (Tuple[FsmState, str]).

## Рефактор-скетч
```python
TRANSITIONS = {
    FsmState.BOOTING: lambda b,p: (FsmState.IDLE,'BOOT_COMPLETE') if b else (FsmState.ERROR_STATE,'BIOS_ERROR')
}
```

## Примеры использования
```python
# 1
handler = FSMHandler(context, state_store)
# 2
new_dto = await handler.process_fsm_dto(current_dto)
# 3
state = handler.process_fsm_state(proto_state)
# 4
next_state, trigger = handler._compute_transition_dto(FsmState.IDLE, True, False)
# 5
logger.info('state', extra={'s': new_dto.state.name})
```

## Тест-хуки/чек-лист
- Смоделировать сценарии переходов для каждого состояния.
- Проверить запись DTO в StateStore и откат при ошибке.
- Убедиться, что legacy метод совпадает по логике с новой версией.

## Вывод
Модуль отвечает за ключевую логику FSM. Неотложно: сократить дублирование и формализовать таблицу переходов. Отложено: улучшить обработку исключений StateStore. В текущем состоянии работоспособен, но требует аккуратного сопровождения.

# СПИСОК ФАЙЛОВ
- services/q_core_agent/core/fsm_handler.py
