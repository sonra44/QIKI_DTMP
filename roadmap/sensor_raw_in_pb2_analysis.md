# СПИСОК ФАЙЛОВ
- generated/sensor_raw_in_pb2.py

## Вход и цель
[Факт] Разбор сообщения `SensorReading` в `sensor_raw_in_pb2.py`.
[Гипотеза] Итог — обзор структуры и рисков.

## Сбор контекста
[Факт] Файл генерируется `protoc` из `sensor_raw_in.proto`.
[Гипотеза] Используется в потоках данных сенсоров.

## Локализация артефакта
[Факт] Путь: `generated/sensor_raw_in_pb2.py`.
[Гипотеза] Применяется как часть службы `QSimAPI`.

## Фактический разбор
- [Факт] Импортирует `common_types_pb2` и `google.protobuf.timestamp_pb2`.
- [Факт] Сообщение `SensorReading` содержит `sensor_id`, `sensor_type`, `timestamp`.
- [Факт] Поле `sensor_data` реализовано как oneof: `vector_data`, `scalar_data`, `binary_data`.
- [Факт] Дополнительные поля: `unit`, `is_valid`, `encoding`, `signal_strength`, `source_module`.
- [Гипотеза] Отсутствие ограничений на размер `binary_data`.

## Роль в системе и связи
[Факт] Представляет универсальный пакет данных сенсора.
[Гипотеза] Может расширяться новыми типами данных.

## Несоответствия и риски
- [Факт] `sensor_type` зависит от enum `SensorType` — несоответствие при изменении (Med).
- [Гипотеза] Нет валидации `signal_strength` (Low).

## Мини-патчи (safe-fix)
[Патч] В `.proto` уточнить диапазон `signal_strength` и размер `binary_data`.

## Примеры использования
```python
# 1. Создание чтения
from generated import sensor_raw_in_pb2
reading = sensor_raw_in_pb2.SensorReading(sensor_id="id1")

# 2. Установка oneof
reading.scalar_data = 42.0

# 3. Проверка активности oneof
assert reading.WhichOneof("sensor_data") == "scalar_data"

# 4. Заполнение времени
from google.protobuf.timestamp_pb2 import Timestamp
reading.timestamp.GetCurrentTime()

# 5. Сериализация
payload = reading.SerializeToString()
```

## Тест-хуки/чек-лист
- [Факт] Проверить `WhichOneof` при разных типах данных.
- [Гипотеза] Тест на размер `binary_data`.
- [Факт] Поле `is_valid` по умолчанию `False`.

## Вывод
1. [Факт] Сообщение покрывает широкие типы данных.
2. [Факт] oneof предотвращает одновременное заполнение нескольких полей.
3. [Гипотеза] Не хватает ограничений на размеры.
4. [Патч] Добавить ограничения в `.proto`.
5. [Факт] Импорты зависят от общих типов и Timestamp.
6. [Гипотеза] Возможность расширений.
7. [Факт] Примеры демонстрируют базовое использование.
8. [Гипотеза] Необходимы тесты на сериализацию.
9. [Факт] Путь и версия задокументированы.
10. [Гипотеза] Отложить расширение до появления новых сенсоров.

# СПИСОК ФАЙЛОВ
- generated/sensor_raw_in_pb2.py
