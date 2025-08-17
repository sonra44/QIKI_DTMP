# actuator_raw_out_pb2.py

## Вход и цель
- Анализ модуля `generated/actuator_raw_out_pb2.py`; итог — обзор, мини-патчи и чек-лист.

## Сбор контекста
- [Факт] Код сгенерирован `protoc`, версия Python runtime 6.31.1.
- [Факт] Импортирует `common_types_pb2` и `google.protobuf.timestamp_pb2`.
- [Гипотеза] Используется для обмена командами с исполнительными механизмами.

## Локализация артефакта
- Путь: `QIKI_DTMP/generated/actuator_raw_out_pb2.py`.
- Генератор: `actuator_raw_out.proto`.

## Фактический разбор
- [Факт] Сообщение `ActuatorCommand` с полями `command_id`, `actuator_id`, `timestamp`.
- [Факт] oneof `command_value`: `float_value`, `int_value`, `bool_value`, `vector_value`.
- [Факт] Enum `CommandType`: `SET_VELOCITY`, `ROTATE`, `ENABLE`, `DISABLE`, `SET_MODE`.
- [Факт] Доп. поля: `unit`, `confidence`, `timeout_ms`, `ack_required`, `retry_count`.

## Роль в системе и связи
- [Факт] Использует типы `UUID`, `Vector3`, `Unit` из `common_types_pb2`.
- [Гипотеза] Формирует команду, которую сервис передаёт контроллерам робота.

## Несоответствия и риски
- [Гипотеза] Отсутствует проверка диапазона для `confidence` (0..1). — Med
- [Гипотеза] Возможна отправка пустого `command_id`. — High

## Мини-патчи (safe-fix)
- [Патч] При формировании сообщений валидировать `command_id` и `actuator_id`.
- [Патч] Ограничить `confidence` в диапазоне 0..1.

## Рефактор-скетч (по желанию)
```python
@dataclass
class ActuatorCommandDTO:
    command_id: str
    actuator_id: str
    value: float
    type: int
```

## Примеры использования
```python
from QIKI_DTMP.generated import actuator_raw_out_pb2 as proto

cmd = proto.ActuatorCommand(
    command_id=proto.common__types__pb2.UUID(value="123"),
    actuator_id=proto.common__types__pb2.UUID(value="456"),
    float_value=1.0,
    command_type=proto.ActuatorCommand.CommandType.SET_VELOCITY,
)
serialized = cmd.SerializeToString()
```

## Тест-хуки/чек-лист
- [ ] Импортируется без ошибок.
- [ ] oneof гарантирует только одно из значений `*_value`.
- [ ] Сериализация/десериализация `ActuatorCommand`.

## Вывод
- Модуль корректно описывает структуру команд, но не ограничивает значения полей.
- Сразу: валидация `command_id` и `confidence`.
- Отложить: использование DTO-обёртки для удобства.
