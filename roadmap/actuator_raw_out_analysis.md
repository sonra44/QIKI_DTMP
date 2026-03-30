## СПИСОК ФАЙЛОВ
- QIKI_DTMP/protos/actuator_raw_out.proto

## Вход и цель
- [Факт] Анализ proto-файла исполнительных команд; итог — обзор и проверочные патч-идеи.

## Сбор контекста
- [Факт] Файл импортирует `common_types.proto` и `google/protobuf/timestamp.proto`.
- [Гипотеза] Используется в подсистемах управления приводами.

## Локализация артефакта
- [Факт] Путь: `QIKI_DTMP/protos/actuator_raw_out.proto`; синтаксис proto3.

## Фактический разбор
- [Факт] Сообщение `ActuatorCommand` содержит поля `command_id`, `actuator_id`, `timestamp`.
- [Факт] `oneof command_value` поддерживает `float`, `int`, `bool`, `Vector3`.
- [Факт] `CommandType` перечисляет шесть типов команд.
- [Факт] Дополнительные параметры: `unit`, `confidence`, `timeout_ms`, `ack_required`, `retry_count`.

## Роль в системе и связи
- [Гипотеза] Формат отправки команд для ROS/GRPC сервисов.
- [Факт] Использует общие типы и временные метки для трассировки.

## Несоответствия и риски
- [Гипотеза][Med] Отсутствие поля для результатов выполнения может усложнить обратную связь.
- [Гипотеза][Low] Нет диапазона допустимых значений для `confidence`.

## Мини-патчи (safe-fix)
- [Патч] Указать диапазон `confidence` через комментарий или валидацию.
- [Патч] Добавить `completion_status` для отчётности результата.

## Рефактор-скетч
```proto
message ActuatorCommandResult {
  qiki.common.UUID command_id = 1;
  bool success = 2;
  string error = 3;
}
```

## Примеры использования
1. ```bash
   protoc -I=. --python_out=. QIKI_DTMP/protos/actuator_raw_out.proto
   ```
2. ```python
   from actuator_raw_out_pb2 import ActuatorCommand
   cmd = ActuatorCommand(actuator_id="a1", command_type=ActuatorCommand.SET_VELOCITY)
   ```
3. ```python
   cmd.float_value = 1.2
   ```
4. ```python
   bytes_data = cmd.SerializeToString()
   ```
5. ```python
   new_cmd = ActuatorCommand.FromString(bytes_data)
   ```

## Тест-хуки/чек-лист
- [Факт] Проверить сериализацию/десериализацию.
- [Факт] Валидировать `command_value` для каждого `CommandType`.

## Вывод
1. [Факт] Структура сообщения проста и ясна.
2. [Гипотеза] Нужна расширенная обратная связь.
3. [Патч] Рассмотреть `ActuatorCommandResult`.
4. [Факт] `oneof` покрывает основные типы значений.
5. [Гипотеза] Возможны проблемы при отсутствии `unit`.
6. [Патч] Сделать `unit` обязательным для некоторых типов.
7. [Факт] `retry_count` поддерживает устойчивость.
8. [Гипотеза] Отсутствует ограничение на `timeout_ms`.
9. [Патч] Ввести минимальные и максимальные значения.
10. [Факт] Документ готов к интеграционному тестированию.

## СПИСОК ФАЙЛОВ
- QIKI_DTMP/protos/actuator_raw_out.proto
