СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/generated/actuator_raw_out_pb2.py
- /home/sonra44/QIKI_DTMP/generated/bios_status_pb2_grpc.py
- /home/sonra44/QIKI_DTMP/generated/bios_status_pb2.py
- /home/sonra44/QIKI_DTMP/generated/common_types_pb2_grpc.py
- /home/sonra44/QIKI_DTMP/generated/common_types_pb2.py
СПИСОК ФАЙЛОВ

# actuator_raw_out_pb2.py — анализ

## Вход и цель
- [Факт] Анализ файла `actuator_raw_out_pb2.py`, содержащего protobuf-описание команды для актуаторов.
- [Гипотеза] Итог — обзор структуры сообщений и рисков.

## Сбор контекста
- [Факт] Файл сгенерирован из `actuator_raw_out.proto` и зависит от `common_types.proto`.
- [Гипотеза] Используется при отправке команд к исполнительным устройствам.

## Локализация артефакта
- [Факт] Путь: `/home/sonra44/QIKI_DTMP/generated/actuator_raw_out_pb2.py`.
- [Факт] Работает с `protobuf` версии 6.31.1.

## Фактический разбор
- [Факт] Импортируются `common_types_pb2` и `google.protobuf.timestamp_pb2`.
- [Факт] Основное сообщение `ActuatorCommand` содержит поля идентификаторов, значения команд и перечисление `CommandType`.
- [Факт] Значения команды расположены в `oneof command_value` (float/int/bool/vector).
- [Гипотеза] Отсутствует явная валидация диапазонов.

## Роль в системе и связи
- [Факт] Сообщение служит контрактом между подсистемой управления и актуаторами.
- [Гипотеза] Вызывается сервисами gRPC, генерирующими команды.

## Несоответствия и риски
- [Гипотеза] Незаполненное поле `unit` может привести к неверной интерпретации (Med).
- [Гипотеза] Отсутствие проверки `retry_count` может вызвать переполнения (Low).

## Мини-патчи (safe-fix)
- [Патч] Установить значение `unit` по умолчанию на стороне сервиса.
- [Патч] Добавить проверку максимального `retry_count`.

## Рефактор-скетч
```python
from qiki.common import UUID, Vector3, Unit
from google.protobuf.timestamp_pb2 import Timestamp
from qiki.actuators import actuator_raw_out_pb2 as ar

cmd = ar.ActuatorCommand(
    command_id=UUID(value="0"*32),
    actuator_id=UUID(value="1"*32),
    timestamp=Timestamp(),
    float_value=1.0,
    unit=Unit.UNIT_UNSPECIFIED,
    command_type=ar.ActuatorCommand.CommandType.SET_VELOCITY,
)
```

## Примеры использования
1. ```python
from qiki.actuators import actuator_raw_out_pb2 as ar
cmd = ar.ActuatorCommand(float_value=3.14)
```
2. ```python
cmd = ar.ActuatorCommand(int_value=5)
```
3. ```python
b = cmd.SerializeToString(); cmd2 = ar.ActuatorCommand.FromString(b)
```
4. ```python
cmd.vector_value.x = 1.0
```
5. ```python
cmd.command_type = ar.ActuatorCommand.CommandType.ENABLE
```

## Тест-хуки/чек-лист
- [Факт] Проверить сериализацию/десериализацию `ActuatorCommand`.
- [Гипотеза] Валидация поля `unit` в бизнес-логике.

## Вывод
1. [Факт] Файл корректно описывает структуру команды актуатора.
2. [Гипотеза] Следует уточнить значения по умолчанию.
3. [Патч] Ограничить `retry_count` и заполнять `unit`.
4. Остальные действия могут быть отложены.

СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/generated/actuator_raw_out_pb2.py
- /home/sonra44/QIKI_DTMP/generated/bios_status_pb2_grpc.py
- /home/sonra44/QIKI_DTMP/generated/bios_status_pb2.py
- /home/sonra44/QIKI_DTMP/generated/common_types_pb2_grpc.py
- /home/sonra44/QIKI_DTMP/generated/common_types_pb2.py
СПИСОК ФАЙЛОВ
