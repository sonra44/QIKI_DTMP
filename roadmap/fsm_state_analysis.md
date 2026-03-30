## СПИСОК ФАЙЛОВ
- QIKI_DTMP/protos/fsm_state.proto

## Вход и цель
- [Факт] Анализ протокола состояний FSM; итог — обзор и чек-лист.

## Сбор контекста
- [Факт] Импортирует `common_types.proto` и `google/protobuf/timestamp.proto`.
- [Гипотеза] Используется для логирования переходов состояния.

## Локализация артефакта
- [Факт] Путь: `QIKI_DTMP/protos/fsm_state.proto`.

## Фактический разбор
- [Факт] Enum `FSMStateEnum` описывает 6 состояний.
- [Факт] Enum `FSMTransitionStatus` описывает результат перехода.
- [Факт] `StateTransition` хранит `timestamp`, `from_state`, `to_state`, `trigger_event`, `status`, `error_message`.
- [Факт] `FsmStateSnapshot` включает `snapshot_id`, `timestamp`, `current_state`, историю переходов, контекстные данные, `fsm_instance_id`, `state_metadata`, `source_module`, `attempt_count`.

## Роль в системе и связи
- [Гипотеза] Служит журналом состояний для анализа и восстановления.
- [Факт] Использует `UUID` и `Timestamp` для идентификации и временной привязки.

## Несоответствия и риски
- [Гипотеза][Med] Нет поля для версии FSM.
- [Гипотеза][Low] Возможны гонки при параллельных обновлениях `attempt_count`.

## Мини-патчи (safe-fix)
- [Патч] Добавить `fsm_version` в `FsmStateSnapshot`.
- [Патч] Прокомментировать требования к целостности `history`.

## Рефактор-скетч
```proto
message FsmStateSnapshot {
  qiki.common.UUID snapshot_id = 1;
  string fsm_version = 2;
  // ... остальные поля
}
```

## Примеры использования
1. ```bash
   protoc -I=. --python_out=. QIKI_DTMP/protos/fsm_state.proto
   ```
2. ```python
   from fsm_state_pb2 import FsmStateSnapshot
   snap = FsmStateSnapshot(current_state=1)
   ```
3. ```python
   tr = snap.history.add(from_state=1, to_state=2, status=1)
   ```
4. ```python
   snap.context_data["battery"] = "low"
   ```
5. ```python
   snap.SerializeToString()
   ```

## Тест-хуки/чек-лист
- [Факт] Проверить корректность истории переходов.
- [Факт] Валидировать значения enum при сериализации.

## Вывод
1. [Факт] Файл фиксирует состояния и переходы.
2. [Гипотеза] Не хватает поля версии.
3. [Патч] Ввести `fsm_version`.
4. [Факт] `context_data` позволяет хранить метаданные.
5. [Гипотеза] Возможен рост истории без очистки.
6. [Патч] Добавить ограничения на размер `history`.
7. [Факт] `attempt_count` отслеживает повторы.
8. [Гипотеза] Нет поля для автора изменений.
9. [Патч] Ввести `changed_by`.
10. [Факт] Подходит для аудита FSM.

## СПИСОК ФАЙЛОВ
- QIKI_DTMP/protos/fsm_state.proto
