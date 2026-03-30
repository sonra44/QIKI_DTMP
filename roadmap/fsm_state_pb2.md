# СПИСОК ФАЙЛОВ
- `QIKI_DTMP/generated/fsm_state_pb2.py`

## Вход и цель
[Факт] Исследование protobuf-модуля состояний FSM. Итог — обзор структур и проверка рисков.

## Сбор контекста
[Факт] Файл генерируется из `fsm_state.proto`. Рядом лежат `common_types_pb2.py` и `timestamp_pb2` для UUID и времени.

## Локализация артефакта
[Факт] `generated/fsm_state_pb2.py`; Python 3.12, Protobuf 6.31.1.

## Фактический разбор
- [Факт] Сообщение `StateTransition` с полями: `timestamp`, `from_state`, `to_state`, `trigger_event`, `status`, `error_message`.
- [Факт] Сообщение `FsmStateSnapshot` содержит `snapshot_id`, `timestamp`, `current_state`, `history`, `context_data`, `fsm_instance_id`, `state_metadata`, `source_module`, `attempt_count`.
- [Факт] Вложенные `ContextDataEntry` и `StateMetadataEntry` реализуют карты ключ-значение.
- [Факт] Enum `FSMStateEnum`: `FSM_STATE_UNSPECIFIED`, `BOOTING`, `IDLE`, `ACTIVE`, `ERROR_STATE`, `SHUTDOWN`.
- [Факт] Enum `FSMTransitionStatus`: `FSM_TRANSITION_STATUS_UNSPECIFIED`, `SUCCESS`, `FAILED`, `PENDING`.

## Роль в системе и связи
[Гипотеза] Используется для сериализации состояния робота; вызывается сервисом `q_core_agent` при сохранении/восстановлении FSM.

## Несоответствия и риски
- [Гипотеза] Отсутствуют ограничения на размер `history` (Med).
- [Гипотеза] `error_message` хранится в plain text без кодов (Low).

## Мини-патчи (safe-fix)
[Патч] Добавить комментарий об очистке `history` для снижения памяти.

## Рефактор-скетч
```python
snapshot = FsmStateSnapshot(
    snapshot_id=common__types__pb2.UUID(),
    current_state=FSMStateEnum.IDLE,
)
```

## Примеры использования
```python
# 1. Создание перехода
tr = StateTransition(from_state=FSMStateEnum.IDLE,
                     to_state=FSMStateEnum.ACTIVE)
```
```python
# 2. Добавление в историю снимка
snap = FsmStateSnapshot(); snap.history.append(tr)
```
```python
# 3. Сериализация
payload = snap.SerializeToString()
```
```python
# 4. Десериализация
dup = FsmStateSnapshot.FromString(payload)
```
```bash
# 5. Проверка enum
python - <<'PY'
from generated import fsm_state_pb2 as fsm
print(list(fsm.FSMStateEnum.keys()))
PY
```

## Тест-хуки / чек-лист
- Создание/сериализация `FsmStateSnapshot` с историей.
- Проверка корректности Enum значений.
- Поведение при пустой или длинной `history`.

## Вывод
1. [Факт] Структура описывает снимок FSM и историю переходов.
2. [Гипотеза] Необходим контроль размера истории.
3. [Патч] Добавить рекомендации по очистке истории.
4. [Факт] Примеры подтверждают сериализацию.
5. [Гипотеза] Возможно расширение `error_message` кодами.
6. [Факт] Использует внешние типы `UUID` и `Timestamp`.
7. [Гипотеза] Может служить базой для логирования состояния.
8. [Факт] Enum значения покрывают основные состояния.
9. [Гипотеза] Слежение за попытками (`attempt_count`) требует политики.
10. [Факт] Код генерируемый, правки в .proto.
