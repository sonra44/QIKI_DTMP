# Отчёт: generated/sensor_raw_in_pb2.py

## Вход и цель
- [Факт] Анализ структуры сообщения `SensorReading` из файла `generated/sensor_raw_in_pb2.py`.

## Сбор контекста
- [Факт] Файл генерируется из `sensor_raw_in.proto`.
- [Факт] Импортирует `common_types_pb2` и `timestamp_pb2`.
- [Гипотеза] Используется во всех сервисах, читающих сырые данные сенсоров.

## Локализация артефакта
- [Факт] Путь: `generated/sensor_raw_in_pb2.py`.
- [Факт] Требуется `protobuf>=6.31.1`.
- [Факт] Подключается как модуль при обработке входящих сообщений.

## Фактический разбор
- [Факт] Сообщение `SensorReading` содержит:
  - `sensor_id` — `qiki.common.UUID`.
  - `sensor_type` — enum `qiki.common.SensorType`.
  - `timestamp` — `google.protobuf.Timestamp`.
  - oneof блок `sensor_data` с полями `vector_data`, `scalar_data`, `binary_data`.
  - Доп. поля: `unit`, `is_valid`, `encoding`, `signal_strength`, `source_module`.
- [Гипотеза] Отсутствует контроль, что только одно поле oneof заполнено.

## Роль в системе и связи
- [Факт] Представляет унифицированный формат показаний для всех модулей.
- [Факт] Используется как ответ метода `GetSensorData` в `QSimAPI`.
- [Гипотеза] Может быть сохранён в хранилище телеметрии.

## Несоответствия и риски
- [Гипотеза][Med] Нет валидации соответствия `unit` и `sensor_type`.
- [Гипотеза][Low] Поле `encoding` свободный текст — возможны расхождения.

## Мини-патчи (safe-fix)
- [Патч][Med] В `.proto` описать допустимые `unit` для каждого `sensor_type`.
- [Патч][Low] Ограничить `encoding` перечислением.

## Рефактор-скетч
- [Гипотеза] Ввести отдельный message `SensorPayload` для расширяемости.

## Примеры использования
```python
from generated import sensor_raw_in_pb2
reading = sensor_raw_in_pb2.SensorReading(sensor_type=1, scalar_data=3.14)
```
```bash
python - <<'PY'
from generated import sensor_raw_in_pb2
print(sensor_raw_in_pb2.SensorReading().HasField('scalar_data'))
PY
```

## Тест-хуки/чек-лист
- [Факт] Проверка oneof: только одно из `vector_data|scalar_data|binary_data` заполнено.
- [Факт] Валидация, что `timestamp` присутствует и >=0.

## Вывод
- Сообщение охватывает основные сценарии, но остаётся риск неконсистентных единиц и кодировок.
- Срочно: документировать связь `sensor_type` ↔ `unit`.
- Отложить: переработать структуру payload для расширяемости.
