# Отчёт по файлу `actuator_raw_out.proto`

## Вход и цель
- [Факт] Анализ `protos/actuator_raw_out.proto`.
- [Факт] Итог: обзор структуры команды исполнительного механизма и рекомендации.

## Сбор контекста
- [Факт] Импортируются `common_types.proto` и `google/protobuf/timestamp.proto`.
- [Факт] В `proposal.proto` сообщение используется как часть `proposed_actions`.
- [Гипотеза] Команды генерируются подсистемой планирования и передаются драйверам.

## Локализация артефакта
- [Факт] Путь: `protos/actuator_raw_out.proto`.
- [Факт] Пакет: `qiki.actuators`.
- [Гипотеза] Используется в gRPC интерфейсе между мозгом и исполнительными модулями.

## Фактический разбор
- [Факт] `message ActuatorCommand` — основная структура команды.
- [Факт] Поля идентификаторов: `command_id`, `actuator_id` (`UUID`).
- [Факт] Метка времени `timestamp`.
- [Факт] `oneof command_value` допускает `float`, `int32`, `bool`, `Vector3`.
- [Факт] Единицы измерения `Unit` и тип `CommandType` (`SET_VELOCITY`, `ROTATE`, ...).
- [Факт] Параметры исполнения: `confidence`, `timeout_ms`, `ack_required`, `retry_count`.

## Роль в системе и связи
- [Факт] Включается в `proposal.proto` для передачи действий.
- [Гипотеза] Может сериализоваться в журнал выполнения команд.

## Несоответствия и риски
- [Гипотеза][Med] Отсутствие ограничений диапазона для числовых значений может привести к неверным параметрам.
- [Гипотеза][Low] Нет явного описания единиц для `command_value` — риск интерпретации.

## Мини-патчи (safe-fix)
- [Патч] Добавить комментарии о допустимых диапазонах `float_value`, `int_value`.
- [Патч] Уточнить связь `unit` с типом значения в комментариях.

## Рефактор-скетч
```proto
message ActuatorCommand {
  UUID command_id = 10;
  UUID actuator_id = 1;
  google.protobuf.Timestamp timestamp = 2;
  CommandPayload payload = 3; // отделяем значение и единицы
  CommandType command_type = 7;
  float confidence = 9;
  int32 timeout_ms = 11;
  bool ack_required = 12;
  int32 retry_count = 13;
}
```

## Примеры использования
```python
cmd = ActuatorCommand(command_id=uuid1(), actuator_id=uuid2(),
                      float_value=1.0, unit=Unit.METERS,
                      command_type=ActuatorCommand.SET_VELOCITY)
```

## Тест-хуки/чек-лист
- Проверить сериализацию и десериализацию `oneof command_value`.
- Валидировать соответствие `unit` и выбранного типа значения.
- Тестировать обработку `timeout_ms` и `retry_count` при ошибках.

## Вывод
- [Факт] Сообщение покрывает базовые потребности управления.
- [Гипотеза] Требуются дополнительные валидации значений и документация единиц.
- [Патч] Добавить описания диапазонов и связи единиц для повышения предсказуемости.
