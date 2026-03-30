СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/generated/actuator_raw_out_pb2.py
- /home/sonra44/QIKI_DTMP/generated/bios_status_pb2_grpc.py
- /home/sonra44/QIKI_DTMP/generated/bios_status_pb2.py
- /home/sonra44/QIKI_DTMP/generated/common_types_pb2_grpc.py
- /home/sonra44/QIKI_DTMP/generated/common_types_pb2.py
СПИСОК ФАЙЛОВ

# common_types_pb2_grpc.py — анализ

## Вход и цель
- [Факт] Модуль для проверки версии gRPC в общих типах.
- [Гипотеза] Итог — рекомендации по окружению.

## Сбор контекста
- [Факт] Импортируется `grpc` и `warnings`; сервисы не объявлены.
- [Гипотеза] Обеспечивает совместимость для других модулей.

## Локализация артефакта
- [Факт] Путь: `/home/sonra44/QIKI_DTMP/generated/common_types_pb2_grpc.py`.
- [Факт] Требует `grpcio>=1.74.0`.

## Фактический разбор
- [Факт] Сравнивает версии и бросает `RuntimeError` при несовпадении.
- [Гипотеза] Используется автоматически при импорте.

## Роль в системе и связи
- [Факт] Гарантирует корректное окружение для общих типов.
- [Гипотеза] Зависимостями являются все protobuf-модули проекта.

## Несоответствия и риски
- [Гипотеза] Жёсткая зависимость от точной версии (Low).

## Мини-патчи (safe-fix)
- [Патч] Разрешить диапазон версий при применении `packaging.version`.

## Рефактор-скетч
```python
import grpc
from qiki.common import common_types_pb2_grpc as ct

print(ct.GRPC_GENERATED_VERSION)
```

## Примеры использования
1. ```python
import common_types_pb2_grpc as ct
```
2. ```python
print(ct.GRPC_VERSION)
```
3. ```python
if ct.GRPC_VERSION < ct.GRPC_GENERATED_VERSION:
    raise SystemExit("grpc too old")
```
4. ```python
try:
    import common_types_pb2_grpc
except RuntimeError:
    pass
```
5. ```bash
python -c "import common_types_pb2_grpc"
```

## Тест-хуки/чек-лист
- [Факт] Импортировать модуль под различными версиями gRPC.

## Вывод
1. [Факт] Модуль выполняет проверку версий.
2. [Гипотеза] Требуется более гибкая политика совместимости.
3. [Патч] Ввести проверку диапазона версий.

СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/generated/actuator_raw_out_pb2.py
- /home/sonra44/QIKI_DTMP/generated/bios_status_pb2_grpc.py
- /home/sonra44/QIKI_DTMP/generated/bios_status_pb2.py
- /home/sonra44/QIKI_DTMP/generated/common_types_pb2_grpc.py
- /home/sonra44/QIKI_DTMP/generated/common_types_pb2.py
СПИСОК ФАЙЛОВ
