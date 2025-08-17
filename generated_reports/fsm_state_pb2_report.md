# Отчёт: `generated/fsm_state_pb2.py`

## Вход и цель
- [Факт] Анализ структуры данных в `generated/fsm_state_pb2.py`.
- [Факт] Итог: обзор сообщений и перечислений FSM.

## Сбор контекста
- [Факт] Файл определяет сообщения `StateTransition` и `FsmStateSnapshot`.
- [Факт] Присутствуют enum `FSMStateEnum` и `FSMTransitionStatus`.
- [Гипотеза] Используется совместно с gRPC сервисами управления состояниями.

## Локализация артефакта
- [Факт] Путь: `generated/fsm_state_pb2.py` (архив `QIKI_DTMP.zip`).
- [Факт] Требует `protobuf` 6.31.1 и зависимости `common_types_pb2`, `timestamp_pb2`.

## Фактический разбор
- [Факт] `StateTransition` описывает переходы: `timestamp`, `from_state`, `to_state`, `trigger_event`, `status`, `error_message`.
- [Факт] `FsmStateSnapshot` содержит `snapshot_id`, `timestamp`, `current_state`, `history`, `context_data`, `fsm_instance_id`, `state_metadata`, `source_module`, `attempt_count`.
- [Факт] `FSMStateEnum`: `BOOTING`, `IDLE`, `ACTIVE`, `ERROR_STATE`, `SHUTDOWN`.
- [Факт] `FSMTransitionStatus`: `SUCCESS`, `FAILED`, `PENDING`.
- [Гипотеза] `context_data` и `state_metadata` используются как произвольные словари.

## Роль в системе и связи
- [Факт] Служит для сериализации состояния FSM между компонентами.
- [Гипотеза] Может сохраняться в БД для восстановления процесса.

## Несоответствия и риски
- [Факт] Нет ограничений на размер `history` и `context_data` (Med).
- [Гипотеза] `attempt_count` может принимать отрицательные значения (Low).

## Мини-патчи (safe-fix)
- [Патч] Добавить проверку длины `history` перед сохранением снимка.
- [Патч] Валидировать `attempt_count` на неотрицательность.

## Рефактор-скетч (по желанию)
```python
# [Патч]
if snapshot.attempt_count < 0:
    snapshot.attempt_count = 0
```

## Примеры использования
```python
# [Факт]
from generated import fsm_state_pb2
snap = fsm_state_pb2.FsmStateSnapshot()
snap.current_state = fsm_state_pb2.FSMStateEnum.IDLE
```

## Тест-хуки/чек-лист
- [Факт] Unit-тест сериализации/десериализации `FsmStateSnapshot`.
- [Гипотеза] Интеграционный тест корректности истории переходов.

## Вывод
- [Факт] Файл задаёт структуры и enum для FSM.
- [Патч] Контроль размера коллекций и значений счётчиков повышает устойчивость.
- [Гипотеза] Хранение снимков в БД можно внедрить позже.
