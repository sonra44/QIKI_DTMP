# `/home/sonra44/QIKI_DTMP/services/q_core_agent/state/types.py`

## Вход и цель
- [Факт] Рассмотреть DTO и enum, описывающие FSM состояния.

## Сбор контекста
- [Факт] Файл не зависит от protobuf, но отражает его структуры.
- [Факт] Соседние модули `store.py` и FSM-обработчики используют эти типы.
- [Гипотеза] Enum синхронизирован с protobuf схемами через ручную поддержку.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/state/types.py`.
- [Факт] Python 3.x, стандартная библиотека (`dataclasses`, `enum`, `time`, `uuid`).
- [Гипотеза] Модуль подгружается при старте Q-Core агента.

## Фактический разбор
- [Факт] Enum `FsmState` и `TransitionStatus` определяют возможные состояния и статусы переходов.
- [Факт] `TransitionDTO` и `FsmSnapshotDTO` — `@dataclass(frozen=True)` с временными метками и UUID.
- [Факт] Функции `initial_snapshot`, `create_transition`, `next_snapshot` помогают генерировать состояния и историю.
- [Гипотеза] `next_snapshot` предполагает редкое обновление версии при неизменном состоянии.

## Роль в системе и связи
- [Факт] Обеспечивает типобезопасный слой между бизнес-логикой и protobuf.
- [Гипотеза] Может использоваться для сериализации в другие форматы (JSON, логирование).

## Несоответствия и риски
- [Факт][Low] Использование `None` для списков/словари требует ручного копирования в `__post_init__`.
- [Гипотеза][Med] Поддержка enum вручную чревата рассинхронизацией с protobuf.

## Мини-патчи (safe-fix)
- [Патч] Заменить `None`-поля на `field(default_factory=list/dict)` для упрощения `__post_init__`.
- [Патч] Добавить автоматический тест сверки enum с protobuf схемой.

## Рефактор-скетч (по желанию)
```python
@dataclass(frozen=True)
class FsmSnapshotDTO:
    history: list[TransitionDTO] = field(default_factory=list)
    context_data: dict[str, str] = field(default_factory=dict)
    state_metadata: dict[str, str] = field(default_factory=dict)
```

## Примеры использования
```python
snap = initial_snapshot()
tr = create_transition(FsmState.BOOTING, FsmState.IDLE, "boot_done")
new_snap = next_snapshot(snap, FsmState.IDLE, "READY", tr)
```

## Тест-хуки/чек-лист
- [Факт] `FsmSnapshotDTO` генерирует уникальные `snapshot_id` и `fsm_instance_id`.
- [Гипотеза] Проверять, что `next_snapshot` не увеличивает версию без смены состояния.

## Вывод
- [Факт] Модуль предоставляет иммутабельные DTO для FSM состояния.
- [Патч] Использовать `default_factory` и добавить тесты сверки enum.
- [Гипотеза] Возможно расширение DTO метаданными без изменения protobuf.
