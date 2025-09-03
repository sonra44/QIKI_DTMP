# СПИСОК ФАЙЛОВ
- services/q_core_agent/core/tick_orchestrator.py

## Вход и цель
Разбор класса `TickOrchestrator`; цель — понять управление тиками и взаимодействие со StateStore.

## Сбор контекста
- [Факт] Импортируются `asyncio`, `time`, `os`, `IDataProvider`, `agent_logger`.
- [Факт] Используются DTO `FsmSnapshotDTO` и `dto_to_proto`.
- [Гипотеза] Конфигурация приходит через `config` агента.

## Локализация артефакта
- Путь: `services/q_core_agent/core/tick_orchestrator.py`
- Окружение: асинхронный Python 3, опционально `AsyncStateStore`.

## Фактический разбор
- [Факт] Класс `TickOrchestrator` имеет методы `run_tick_async`, `_handle_fsm_with_state_store`, `run_tick`.
- [Факт] `run_tick_async` разбивает работу на пять фаз (context, BIOS, FSM, proposals, decision) и логирует время.
- [Факт] `_handle_fsm_with_state_store` получает и обновляет состояние через StateStore, конвертируя DTO в protobuf.
- [Факт] `run_tick` — синхронный легаси метод с аналогичной логикой.

## Роль в системе и связи
- [Факт] Центральный координационный модуль тика QCoreAgent.
- [Гипотеза] Используется агентом в основном цикле; ошибки переключают в safe‑mode.

## Несоответствия и риски
- [Гипотеза][Med] Отсутствует ограничение времени на `_handle_fsm_with_state_store`.
- [Гипотеза][Low] Повторение кода фаз между async и legacy версиями.

## Мини-патчи (safe-fix)
- [Патч] Добавить timeout для `_handle_fsm_with_state_store`.
- [Патч] Вынести расчёт phase durations в отдельную функцию.

## Рефактор-скетч
```python
async def run_tick_async(self, provider):
    phases = [self.agent._update_context_without_fsm, self.agent._handle_bios]
    for fn in phases:
        start = time.time(); fn(provider); log(start)
```

## Примеры использования
```python
# 1
orch = TickOrchestrator(agent, {}, state_store)
# 2
await orch.run_tick_async(provider)
# 3
orch.run_tick(provider)
# 4
os.environ['QIKI_USE_STATESTORE'] = 'true'
# 5
await orch._handle_fsm_with_state_store()
```

## Тест-хуки/чек-лист
- Смоделировать успешный и провальный tick.
- Проверить, что state_store обновляется.
- Проверить вывод логов фаз.

## Вывод
Класс аккуратно разделяет async и legacy сценарии. Срочно: добавить таймауты и уменьшить дублирование кода. Отложено: унифицировать обработку ошибок и конфигурируемые паузы. В целом модуль зрелый, но требует упрощения.

# СПИСОК ФАЙЛОВ
- services/q_core_agent/core/tick_orchestrator.py
