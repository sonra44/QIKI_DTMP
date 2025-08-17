# common_types_pb2.py

## Вход и цель
- Анализ модуля `generated/common_types_pb2.py`; итог — обзор базовых типов.

## Сбор контекста
- [Факт] Генерация `protoc`, runtime 6.31.1.
- [Факт] Импортирует `google.protobuf.timestamp_pb2`.
- [Гипотеза] Используется всеми другими protobuf‑модулями как общий словарь типов.

## Локализация артефакта
- Путь: `QIKI_DTMP/generated/common_types_pb2.py`.
- Исходник: `common_types.proto`.

## Фактический разбор
- [Факт] Сообщение `UUID` (строковое поле `value`).
- [Факт] Сообщение `Vector3` (`x`, `y`, `z` как float).
- [Факт] Enum `SensorType` (`LIDAR`, `IMU`, `CAMERA`, `GPS`, `THERMAL`).
- [Факт] Enum `ActuatorType` (`WHEEL_MOTOR`, `SERVO`, `GRIPPER`, `ARM`).
- [Факт] Enum `Unit` (`METERS`, `DEGREES`, `PERCENT`, `VOLTS`, `AMPS`, `WATTS`, `MILLISECONDS`, `KELVIN`, `BAR`).

## Роль в системе и связи
- [Факт] Предоставляет типы для остальных protobuf сообщений (например, `ActuatorCommand`).
- [Гипотеза] Определяет стандартные единицы измерения и идентификаторы.

## Несоответствия и риски
- [Гипотеза] `UUID.value` не проверяется на формат. — Med
- [Гипотеза] `Vector3` не ограничивает диапазон значений. — Low

## Мини-патчи (safe-fix)
- [Патч] При создании `UUID` валидировать формат UUIDv4.
- [Патч] Ввести функцию нормализации для `Vector3` при необходимости.

## Рефактор-скетч (по желанию)
```python
@dataclass(frozen=True)
class Vector3:
    x: float
    y: float
    z: float
```

## Примеры использования
```python
from QIKI_DTMP.generated import common_types_pb2 as ct

v = ct.Vector3(x=1.0, y=2.0, z=3.0)
uid = ct.UUID(value="123e4567-e89b-12d3-a456-426614174000")
```

## Тест-хуки/чек-лист
- [ ] Импорт без ошибок.
- [ ] Проверка сериализации `UUID` и `Vector3`.
- [ ] Enum значения соответствуют ожиданиям.

## Вывод
- Модуль задаёт базовые типы и перечисления; критичных проблем нет.
- Сразу: валидация строк UUID.
- Отложить: введение dataclass‑обёрток.
