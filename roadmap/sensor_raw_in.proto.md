# СПИСОК ФАЙЛОВ
- protos/sensor_raw_in.proto

## Вход и цель
Описание структуры сообщения `SensorReading` для стандартизации входящих данных. Итог — обзор и выявление рисков.

## Сбор контекста
- [Факт] Импорты: `common_types.proto`, `google/protobuf/timestamp.proto`.
- [Факт] `SensorReading` использует `oneof sensor_data`.
- [Гипотеза] Файл применяется в моделировании сенсорных показаний.

## Локализация артефакта
- [Факт] Путь: `QIKI_DTMP/protos/sensor_raw_in.proto`.
- [Факт] Доступен из других протоколов (`q_sim_api.proto`).

## Фактический разбор
- [Факт] Поля: `sensor_id`, `sensor_type`, `timestamp`, `sensor_data`, `unit`, `is_valid`, `encoding`, `signal_strength`, `source_module`.
- [Факт] `oneof sensor_data` включает `vector_data`, `scalar_data`, `binary_data`.
- [Гипотеза] Отсутствует поле для метаданных изображения (размеры и т.п.).

## Роль в системе и связи
- [Факт] Служит универсальным контейнером данных с сенсоров.
- [Гипотеза] Используется всеми модулями, получающими сенсорную информацию.

## Несоответствия и риски
- [Гипотеза][Med] Нет указания порядка байтов для `binary_data`.
- [Гипотеза][Low] Не определены допустимые диапазоны `signal_strength`.

## Мини-патчи (safe-fix)
- [Патч] Добавить комментарий о диапазоне `signal_strength` (0.0–1.0).
- [Патч] Уточнить описание `encoding` для бинарных данных.

## Рефактор-скетч
```proto
message SensorReading {
  qiki.common.UUID sensor_id = 1;
  qiki.common.SensorType sensor_type = 2;
  google.protobuf.Timestamp timestamp = 3;
  oneof sensor_data {
    qiki.common.Vector3 vector_data = 4;
    float scalar_data = 5;
    bytes binary_data = 7;
  }
  qiki.common.Unit unit = 6;
  bool is_valid = 8;
  string encoding = 9;
  float signal_strength = 10; // 0.0-1.0
  string source_module = 11;
}
```

## Примеры использования
1. ```bash
python -m grpc_tools.protoc -I protos --python_out=. protos/sensor_raw_in.proto
```
2. ```python
from qiki import sensor_raw_in_pb2 as sensors
reading = sensors.SensorReading(sensor_id=uuid, sensor_type=1)
```
3. ```python
reading.vector_data.x = 0.1
reading.is_valid = True
```
4. ```python
serialized = reading.SerializeToString()
```
5. ```python
parsed = sensors.SensorReading.FromString(serialized)
```

## Тест-хуки/чек-лист
- Валидация `oneof` — только одно поле активно.
- Проверка корректности `UUID` и `timestamp`.
- Сериализация/десериализация без потерь.

## Вывод
Сообщение охватывает большинство сценариев передачи сырых данных. Срочно стоит задокументировать диапазоны и кодировки. Расширение метаданных можно отложить до появления конкретных требований.
