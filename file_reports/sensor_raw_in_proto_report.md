# Отчет по файлу `protos/sensor_raw_in.proto`

## Вход и цель
- [Факт] Требуется анализ структуры сообщения `SensorReading` для дальнейшего использования и тестов.

## Сбор контекста
- [Факт] Файл импортирует `common_types.proto` и `google/protobuf/timestamp.proto`.
- [Гипотеза] `common_types.proto` содержит определения `UUID`, `SensorType`, `Vector3` и `Unit`.

## Локализация артефакта
- [Факт] Путь: `protos/sensor_raw_in.proto`.
- [Факт] Используется синтаксис `proto3` и пакет `qiki.sensors`.

## Фактический разбор
- [Факт] Сообщение `SensorReading` включает идентификатор сенсора `sensor_id` и тип `sensor_type`.
- [Факт] Поле `timestamp` фиксирует время измерения.
- [Факт] Данные передаются через `oneof sensor_data` с вариантами `vector_data`, `scalar_data` или `binary_data`.
- [Факт] Дополнительные поля: `unit`, `is_valid`, `encoding`, `signal_strength`, `source_module`.

## Роль в системе и связи
- [Гипотеза] Сообщение служит универсальным контейнером для показаний разных сенсоров, используемым сервисом Q-Sim.
- [Факт] Поля дают возможность отслеживать источник и качество данных.

## Несоответствия и риски
- [Гипотеза] Отсутствие ограничений на размер `binary_data` может привести к перегрузке канала — приоритет High.
- [Гипотеза] Не описаны допустимые диапазоны `signal_strength` — приоритет Medium.
- [Гипотеза] `encoding` не нормализован (нет enum) — приоритет Low.

## Мини-патчи (safe-fix)
- [Патч] Добавить комментарии о максимальном размере `binary_data` и диапазоне `signal_strength`.
- [Патч] Рассмотреть enum для поля `encoding`.

## Рефактор-скетч (по желанию)
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
  string encoding = 9; // TODO: сделать enum
  float signal_strength = 10;
  string source_module = 11;
}
```

## Примеры использования
- [Факт] Пример сериализации в Python: `SensorReading(sensor_id=..., scalar_data=42.0)`.
- [Гипотеза] Использование в gRPC-сообщении для передачи показаний IMU.

## Тест-хуки/чек-лист
- [Факт] Тест на корректную работу `oneof`: одновременно установлено только одно поле данных.
- [Гипотеза] Проверка обработки больших `binary_data` и некорректных значений `signal_strength`.

## Вывод
- [Факт] Сообщение обеспечивает гибкую структуру для разных типов сенсоров.
- [Гипотеза] Требуются ограничения и уточнения метаданных для предотвращения ошибок на ранних этапах.
