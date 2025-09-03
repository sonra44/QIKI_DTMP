# СПИСОК ФАЙЛОВ
- services/q_core_agent/state/conv.py

## Вход и цель
Анализ модуля конвертации DTO⇄protobuf; цель — понять маппинг и возможные ошибки.

## Сбор контекста
- [Факт] Импорты: protobuf `Timestamp`, `UUID`, типы DTO, `MessageToDict`.
- [Факт] Определены маппинги enum'ов и статусы переходов.
- [Гипотеза] Используется в логгере и при обмене с внешними сервисами.

## Локализация артефакта
- Путь: `services/q_core_agent/state/conv.py`
- Окружение: Python с установленными protobuf.

## Фактический разбор
- [Факт] Функции `_create_uuid_proto`, `_extract_uuid_string`, `_timestamp_to_float`, `_float_to_timestamp`.
- [Факт] Основные API: `transition_dto_to_proto`, `transition_proto_to_dto`, `dto_to_proto`, `proto_to_dto`, `dto_to_json_dict`, `dto_to_protobuf_json`, `create_proto_snapshot`, `parse_proto_snapshot`.
- [Факт] Объявлен `ConversionError` для ошибок.

## Роль в системе и связи
- [Факт] Связывает внутренние DTO и внешний protobuf слой.
- [Гипотеза] Критичен для совместимости логов и сетевого протокола.

## Несоответствия и риски
- [Гипотеза][Med] Отсутствует кеширование при множественных конвертациях.
- [Гипотеза][Low] Возможна потеря `ts_mono` при переходе через protobuf.

## Мини-патчи (safe-fix)
- [Патч] Добавить проверку на overflow секунд в `_float_to_timestamp`.
- [Патч] Логировать ошибки конвертации с контекстом DTO.

## Рефактор-скетч
```python
def dto_to_proto(dto):
    return FsmStateSnapshot(
        snapshot_id=_create_uuid_proto(dto.snapshot_id),
        current_state=FSM_STATE_DTO_TO_PROTO[dto.state]
    )
```

## Примеры использования
```python
# 1
proto = dto_to_proto(FsmSnapshotDTO(version=1, state=FsmState.IDLE))
# 2
dto = proto_to_dto(proto)
# 3
transition_proto = transition_dto_to_proto(create_transition(FsmState.IDLE, FsmState.ACTIVE, 'X'))
# 4
json_dict = dto_to_json_dict(dto)
# 5
MessageToDict(dto_to_proto(dto))
```

## Тест-хуки/чек-лист
- Конвертация DTO→proto→DTO сохраняет данные.
- Проверить обработку невалидных UUID и временных меток.
- Замерить производительность при больших историях.

## Вывод
Модуль тщательно покрывает конвертации. Срочно: добавить валидацию временных диапазонов и расширенный лог ошибок. Отложено: оптимизировать кеширование и поддержать `ts_mono` в protobuf. В текущем виде подходит для большинства сценариев.

# СПИСОК ФАЙЛОВ
- services/q_core_agent/state/conv.py
