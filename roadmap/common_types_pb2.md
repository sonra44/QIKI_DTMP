СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/generated/actuator_raw_out_pb2.py
- /home/sonra44/QIKI_DTMP/generated/bios_status_pb2_grpc.py
- /home/sonra44/QIKI_DTMP/generated/bios_status_pb2.py
- /home/sonra44/QIKI_DTMP/generated/common_types_pb2_grpc.py
- /home/sonra44/QIKI_DTMP/generated/common_types_pb2.py
СПИСОК ФАЙЛОВ

# common_types_pb2.py — анализ

## Вход и цель
- [Факт] Содержит общие типы: UUID, Vector3, перечисления для сенсоров/актуаторов/единиц измерения.
- [Гипотеза] Итог — обзор базовых структур.

## Сбор контекста
- [Факт] Зависит от `timestamp_pb2`.
- [Гипотеза] Используется большинством модулей системы.

## Локализация артефакта
- [Факт] Путь: `/home/sonra44/QIKI_DTMP/generated/common_types_pb2.py`.
- [Факт] Protobuf 6.31.1.

## Фактический разбор
- [Факт] Определены сообщения `UUID`, `Vector3`.
- [Факт] Enum `SensorType`, `ActuatorType`, `Unit` описывают базовые константы.
- [Гипотеза] Нет алиасов для пользовательских единиц.

## Роль в системе и связи
- [Факт] Является фундаментом всех других сообщений.
- [Гипотеза] Несовместимость здесь затронет весь проект.

## Несоответствия и риски
- [Гипотеза] Отсутствие проверки формата строки UUID (Med).
- [Гипотеза] Неполный список единиц измерения (Low).

## Мини-патчи (safe-fix)
- [Патч] Добавить валидацию UUID на уровне бизнес-логики.
- [Патч] Расширить enum `Unit` при необходимости.

## Рефактор-скетч
```python
from qiki.common import common_types_pb2 as ct
u = ct.UUID(value="1234")
v = ct.Vector3(x=1.0, y=2.0, z=3.0)
```

## Примеры использования
1. ```python
uid = ct.UUID(value="abcd")
```
2. ```python
vec = ct.Vector3(x=0.0, y=1.0, z=2.0)
```
3. ```python
type = ct.SensorType.LIDAR
```
4. ```python
atype = ct.ActuatorType.GRIPPER
```
5. ```python
unit = ct.Unit.METERS
```

## Тест-хуки/чек-лист
- [Факт] Валидация допустимости строк UUID.
- [Гипотеза] Тест на сериализацию `Vector3`.

## Вывод
1. [Факт] Файл предоставляет базовые структуры для всего проекта.
2. [Гипотеза] Стоит расширить проверки корректности.
3. [Патч] Ввести валидацию UUID и дополнить `Unit`.

СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/generated/actuator_raw_out_pb2.py
- /home/sonra44/QIKI_DTMP/generated/bios_status_pb2_grpc.py
- /home/sonra44/QIKI_DTMP/generated/bios_status_pb2.py
- /home/sonra44/QIKI_DTMP/generated/common_types_pb2_grpc.py
- /home/sonra44/QIKI_DTMP/generated/common_types_pb2.py
СПИСОК ФАЙЛОВ
