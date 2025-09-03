# СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/state/store.py

## Вход и цель
[Факт] Модуль реализует `AsyncStateStore` — потокобезопасное хранилище FSM.
[Гипотеза] Используется в Q-Core для обмена состоянием между обработчиком и внешними клиентами.

## Сбор контекста
[Факт] Импортируются `asyncio`, `logging`, `time`, `replace` и DTO из `types.py`.
[Гипотеза] Соседний модуль `conv.py` конвертирует DTO в protobuf и обратно.

## Локализация артефакта
[Факт] Путь: `services/q_core_agent/state/store.py` в проекте `QIKI_DTMP`.
[Факт] Выполняется на Python 3.12 в асинхронном окружении.

## Фактический разбор
- [Факт] Исключения `StateStoreError` и `StateVersionError` описывают ошибки работы.
- [Факт] Класс `AsyncStateStore` хранит снапшот и список подписчиков.
- [Факт] Методы: `get`, `get_with_meta`, `set`, `subscribe`, `unsubscribe`, `_notify_subscribers`, `initialize_if_empty`.
- [Факт] Метрики собираются в словаре `_metrics`.

## Роль в системе и связи
[Гипотеза] Является SSOT состояния: один писатель (FSM), множество читателей через gRPC/CLI.

## Несоответствия и риски
- [Факт] В `_notify_subscribers` удаление мёртвых очередей не логируется — приоритет Low.
- [Гипотеза] Нет ограничения на рост `history` в `FsmSnapshotDTO` — приоритет Med.
- [Гипотеза] Метрики не экспортируются наружу — приоритет Low.

## Мини-патчи (safe-fix)
- [Патч] Добавить логирование количества удалённых подписчиков.
- [Патч] В `set` логировать конфликты версий уровнем `warning`.

## Рефактор-скетч
```python
class SimpleStore:
    def __init__(self, snap=None):
        self._snap = snap
    async def get(self):
        return self._snap
```

## Примеры использования
1. ```python
import asyncio
from services.q_core_agent.state.store import AsyncStateStore
async def main():
    store = AsyncStateStore()
    await store.initialize_if_empty()
    print(await store.get())
asyncio.run(main())
```
2. ```python
from services.q_core_agent.state.store import AsyncStateStore
from services.q_core_agent.state.types import initial_snapshot
store = AsyncStateStore(initial_snapshot())
```
3. ```python
import asyncio
from services.q_core_agent.state.store import AsyncStateStore
from services.q_core_agent.state.types import initial_snapshot
async def set_demo():
    store = AsyncStateStore(initial_snapshot())
    snap = await store.get()
    await store.set(snap)
asyncio.run(set_demo())
```
4. ```python
import asyncio
from services.q_core_agent.state.store import AsyncStateStore
async def sub_demo():
    store = AsyncStateStore()
    q = await store.subscribe('demo')
    await store.initialize_if_empty()
    print(await q.get())
asyncio.run(sub_demo())
```
5. ```python
import asyncio
from services.q_core_agent.state.store import AsyncStateStore
async def version_demo():
    store = AsyncStateStore()
    snap = await store.initialize_if_empty()
    await store.set(snap, enforce_version=True)
asyncio.run(version_demo())
```

## Тест-хуки/чек-лист
- [ ] Параллельные `set` и `get` не блокируют друг друга.
- [ ] Конфликт версий вызывает `StateVersionError`.
- [ ] Новый подписчик получает текущее состояние сразу.
- [ ] Очередь подписчика очищается при переполнении.
- [ ] `initialize_if_empty` создаёт COLD_START только один раз.

## Вывод
1. [Факт] Реализовано потокобезопасное хранение снапшота.
2. [Факт] Подписчики обслуживаются через `asyncio.Queue`.
3. [Факт] Поддерживается версионирование снапшотов.
4. [Гипотеза] Метрики могут быть использованы для мониторинга.
5. [Гипотеза] Не хватает лимитов на длину истории.
6. [Патч] Добавить логирование удалённых подписчиков.
7. [Патч] Выводить предупреждение при конфликте версий.
8. [Гипотеза] Стоит вынести метрики в отдельный модуль.
9. [Гипотеза] Возможно добавить persistence на диск.
10. [Факт] Код готов к дальнейшим расширениям.
