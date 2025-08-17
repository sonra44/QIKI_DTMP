# Отчёт по файлу `fsm_state.proto`

## Вход и цель
- [Факт] Анализ `protos/fsm_state.proto`.
- [Факт] Цель: описание состояния конечного автомата и истории переходов.

## Сбор контекста
- [Факт] Импортирует `common_types.proto` и `google/protobuf/timestamp.proto`.
- [Факт] Определяет перечисления `FSMStateEnum`, `FSMTransitionStatus`, сообщения `StateTransition`, `FsmStateSnapshot`.
- [Гипотеза] Используется системами управления для отслеживания состояния.

## Локализация артефакта
- [Факт] Путь: `protos/fsm_state.proto`.
- [Факт] Пакет: `qiki.fsm`.
- [Гипотеза] Снимки состояния передаются в систему логирования.

## Фактический разбор
- [Факт] `FSMStateEnum` включает состояния `BOOTING`, `IDLE`, `ACTIVE`, `ERROR_STATE`, `SHUTDOWN`.
- [Факт] `StateTransition` фиксирует переходы: время, исходное и новое состояние, событие, статус и сообщение об ошибке.
- [Факт] `FsmStateSnapshot` содержит `snapshot_id`, `timestamp`, `current_state`, `history`, `context_data`, `fsm_instance_id`, `state_metadata`, `source_module`, `attempt_count`.

## Роль в системе и связи
- [Факт] Позволяет отслеживать развитие состояния FSM во времени.
- [Гипотеза] История используется для диагностики и восстановления.

## Несоответствия и риски
- [Гипотеза][Med] `context_data` и `state_metadata` как `map<string,string>` могут хранить несогласованные ключи.
- [Гипотеза][Low] Отсутствие ограничений размера истории может привести к росту сообщений.

## Мини-патчи (safe-fix)
- [Патч] Ограничить размер `history` или предусмотреть обрезку при сериализации.
- [Патч] Документировать допустимые ключи в `context_data`/`state_metadata`.

## Рефактор-скетч
```proto
message FsmStateSnapshot {
  UUID snapshot_id = 1;
  FSMStateEnum current_state = 3;
  repeated StateTransition recent_history = 4;
}
```

## Примеры использования
```python
snap = FsmStateSnapshot(snapshot_id=uuid1(), current_state=FSMStateEnum.ACTIVE)
snap.history.extend([StateTransition(from_state=FSMStateEnum.IDLE, to_state=FSMStateEnum.ACTIVE, status=FSMTransitionStatus.SUCCESS)])
```

## Тест-хуки/чек-лист
- Проверить корректность записи переходов и статусов.
- Валидировать уникальность `snapshot_id`.
- Тестировать обработку пустой истории и заполненных `context_data`.

## Вывод
- [Факт] Файл описывает структуру для управления и отслеживания FSM.
- [Гипотеза] Требуются ограничения для карт и истории.
- [Патч] Рекомендуется документировать ключи и ограничить размер истории.
