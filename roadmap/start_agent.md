СПИСОК ФАЙЛОВ
- scripts/start_agent.sh

## Вход и цель
- [Факт] Скрипт запускает Q-Core Agent с gRPC.
- [Гипотеза] Используется разработчиком для локального запуска агента.

## Сбор контекста
- [Факт] Проанализирован `start_agent.sh` и связанные директории `generated`, `protos`.
- [Гипотеза] Требует запущенного симулятора `start_sim.sh`.

## Локализация артефакта
- [Факт] `scripts/start_agent.sh` в корне проекта.
- [Гипотеза] Работает из любой директории при корректной структуре проекта.

## Фактический разбор
- [Факт] Проверяет наличие `python3` и пакета `grpc`.
- [Факт] При отсутствии сгенерированных protobuf файлов запускает `grpc_tools.protoc`.
- [Факт] Перед стартом обращается к Q-Sim на `localhost:50051` и вызывает `HealthCheck`.
- [Факт] В случае успеха запускает `python3 services/q_core_agent/main.py --grpc`.
- [Гипотеза] `main.py` реализует основной цикл агента.

## Роль в системе и связи
- [Факт] Зависит от результата `start_sim.sh` (доступность сервера).
- [Гипотеза] Используется как точка входа для тестирования полного стека.

## Несоответствия и риски
- [Гипотеза] Отсутствие проверки наличия файла `generated/q_sim_api_pb2_grpc.py`.
- [Гипотеза] Жёстко задан порт `50051`; конфликт портов не обрабатывается.

## Мини-патчи (safe-fix)
- [Патч] Добавить проверку на существование `grpc_tools.protoc`.
- [Патч] Параметризовать адрес Q-Sim через переменные окружения.

## Рефактор-скетч
```bash
#!/bin/bash
set -e
: "${QSIM_ADDR:=localhost:50051}"
python3 - <<PY
import grpc
from generated.q_sim_api_pb2_grpc import QSimAPIStub
from google.protobuf.empty_pb2 import Empty
channel = grpc.insecure_channel('$QSIM_ADDR')
QSimAPIStub(channel).HealthCheck(Empty(), timeout=3)
PY
python3 services/q_core_agent/main.py --grpc
```

## Примеры использования
1. `bash scripts/start_agent.sh`
2. `QSIM_ADDR=localhost:60000 bash scripts/start_agent.sh`
3. `python3 services/q_core_agent/main.py --grpc`
4. `python3 -m grpc_tools.protoc --proto_path=protos --python_out=generated protos/q_sim_api.proto`
5. `python3 - <<'PY'\nimport grpc\nprint(grpc.__version__)\nPY`

## Тест-хуки/чек-лист
- Проверить запуск при работающем `start_sim.sh`.
- Убедиться, что при отсутствии gRPC пакетов выводится понятная ошибка.
- Валидация повторного запуска без пересоздания protobuf файлов.
- Проверка корректности закрытия соединения с Q-Sim.
- Тестировать поведение при недоступном порту.

## Вывод
1. Скрипт автоматизирует запуск агента с gRPC.
2. Зависит от внешнего сервиса Q-Sim.
3. Нужна дополнительная валидация зависимостей.
4. Адрес сервера жёстко прописан.
5. Доступна генерация protobuf при первом запуске.
6. Пример команд демонстрирует гибкость.
7. Возможны расширения для Docker/k8s.
8. Следует вынести параметры в конфиг.
9. Текущая реализация достаточна для локального теста.
10. Рекомендуется улучшить обработку ошибок соединения.

СПИСОК ФАЙЛОВ
- scripts/start_agent.sh
