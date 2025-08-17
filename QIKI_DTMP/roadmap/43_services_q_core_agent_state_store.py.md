# `/home/sonra44/QIKI_DTMP/services/q_core_agent/state/store.py`

## Вход и цель
- [Факт] Проанализировать модуль `store.py` и подготовить обзор по схеме.

## Сбор контекста
- [Факт] Использует `asyncio`, `logging`, `dataclasses.replace` и DTO из `types.py`.
- [Факт] В соседнем `types.py` определены `FsmSnapshotDTO` и `initial_snapshot`.
- [Гипотеза] Модуль применяется внутри FSM-обработчика как единственный писатель состояния.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/state/store.py`.
- [Факт] Окружение: Python 3.x, зависимости `grpcio>=1.62.0` указаны в `requirements.txt`.
- [Гипотеза] Запускается в составе Q-Core агента как in-memory сервис.

## Фактический разбор
- [Факт] Класс `AsyncStateStore` обеспечивает потокобезопасный доступ к `FsmSnapshotDTO` через `asyncio.Lock`.
- [Факт] Методы: `get`, `get_with_meta`, `set`, `subscribe`, `unsubscribe`, `_notify_subscribers`, `initialize_if_empty`.
- [Факт] При `set` возможен автоинкремент версии и уведомление всех подписчиков.
- [Гипотеза] Метрики в `_metrics` могут служить источником для Prometheus.

## Роль в системе и связи
- [Факт] Выполняет роль SSOT (Single Source of Truth) для FSM состояния.
- [Гипотеза] Подписчики — gRPC сервисы, CLI или логгеры, ожидающие уведомления через `asyncio.Queue`.

## Несоответствия и риски
- [Факт][Med] Уведомление подписчиков выполняется внутри захваченного `Lock`, что может задерживать операции `get`.
- [Гипотеза][Low] Возможна утечка очередей при падении подписчика без вызова `unsubscribe`.

## Мини-патчи (safe-fix)
- [Патч] Вызов `_notify_subscribers` вынести за пределы блока `async with self._lock` для снижения задержек.
- [Патч] Добавить таймаут/финализацию для `unsubscribe`, чтобы чистить неиспользуемые очереди.

## Рефактор-скетч (по желанию)
```python
class AsyncStateStore:
    async def set(self, snap, enforce_version=False):
        async with self._lock:
            snap = self._apply_version(snap, enforce_version)
            self._snap = snap
        await self._notify_subscribers(snap)
```

## Примеры использования
```python
store = AsyncStateStore()
await store.initialize_if_empty()
queue = await store.subscribe("logger")
await store.set(next_snap, enforce_version=True)
```

## Тест-хуки/чек-лист
- [Факт] `set` повышает версию при одинаковом состоянии.
- [Факт] Подписчики получают первое состояние сразу после подписки.
- [Гипотеза] Проверить удаление мёртвых очередей при `_notify_subscribers`.

## Вывод
- [Факт] Модуль реализует асинхронное хранилище с Pub/Sub и метриками.
- [Патч] Вынести уведомления за пределы блокировки и добавить очистку очередей.
- [Гипотеза] Дальнейшее развитие — экспорт метрик в систему мониторинга.
