# СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/state/types.py

## Вход и цель
[Факт] Файл описывает immutable DTO для FSM и вспомогательные функции.
[Гипотеза] Служит слоем между protobuf и бизнес-логикой.

## Сбор контекста
[Факт] Используются `dataclass`, `IntEnum`, `uuid` и `time`.
[Факт] Внутри определены `FsmState`, `TransitionStatus`, `TransitionDTO`, `FsmSnapshotDTO`.
[Гипотеза] Модуль `conv.py` сериализует эти DTO в протобы.

## Локализация артефакта
[Факт] Путь: `services/q_core_agent/state/types.py`.
[Факт] Не имеет внешних зависимостей на protobuf.

## Фактический разбор
- [Факт] `FsmState` и `TransitionStatus` — перечисления на базе `IntEnum`.
- [Факт] `TransitionDTO` и `FsmSnapshotDTO` заморожены (`frozen=True`).
- [Факт] Функция `initial_snapshot` создаёт стартовое состояние.
- [Факт] Функция `create_transition` упрощает создание переходов.
- [Факт] Функция `next_snapshot` строит новый снапшот из текущего.

## Роль в системе и связи
[Гипотеза] DTO используют обработчики FSM и `AsyncStateStore` для передачи состояния без protobuf.

## Несоответствия и риски
- [Факт] Поля `context_data` и `state_metadata` не типизированы по ключам — приоритет Low.
- [Гипотеза] Нет проверки уникальности `snapshot_id` — приоритет Low.
- [Гипотеза] `history` может расти без ограничений — приоритет Med.

## Мини-патчи (safe-fix)
- [Патч] Явно указать типы словарей: `Dict[str, str]`.
- [Патч] Добавить параметр ограничения длины `history` в `next_snapshot`.

## Рефактор-скетч
```python
@dataclass(frozen=True)
class Snapshot:
    version: int
    state: FsmState
```

## Примеры использования
1. ```python
from services.q_core_agent.state.types import initial_snapshot
snap = initial_snapshot()
```
2. ```python
from services.q_core_agent.state.types import FsmState, create_transition
tr = create_transition(FsmState.BOOTING, FsmState.IDLE, 'boot_done')
```
3. ```python
from services.q_core_agent.state.types import next_snapshot, FsmState, initial_snapshot
cur = initial_snapshot()
new = next_snapshot(cur, FsmState.IDLE, 'init complete')
```
4. ```python
from services.q_core_agent.state.types import FsmSnapshotDTO, FsmState
snap = FsmSnapshotDTO(version=1, state=FsmState.ACTIVE, reason='demo')
```
5. ```python
from services.q_core_agent.state.types import TransitionDTO, FsmState
tr = TransitionDTO(from_state=FsmState.IDLE, to_state=FsmState.ACTIVE, trigger_event='start')
```

## Тест-хуки/чек-лист
- [ ] `initial_snapshot` всегда возвращает `version=0` и `state=BOOTING`.
- [ ] `next_snapshot` увеличивает `version` только при смене состояния.
- [ ] `TransitionDTO` автоматически заполняет временные метки.
- [ ] UUIDы уникальны между снапшотами.
- [ ] История переходов копируется без побочных эффектов.

## Вывод
1. [Факт] DTO изолируют FSM от protobuf-зависимостей.
2. [Факт] Все структуры иммутабельны.
3. [Факт] Предоставлены фабрики для стартовых и следующих состояний.
4. [Гипотеза] Ограничение `history` следует реализовать на уровне хранилища.
5. [Гипотеза] Возможна оптимизация хранения UUID.
6. [Патч] Уточнить типы словарей.
7. [Патч] Добавить лимит на длину истории.
8. [Гипотеза] Можно добавить методы сравнения снапшотов.
9. [Гипотеза] Стоит описать сериализацию в JSON.
10. [Факт] Модуль готов к интеграции.
