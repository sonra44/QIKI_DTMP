# СПИСОК ФАЙЛОВ
- protos/q_sim_api.proto

## Вход и цель
Кратко описать сервис gRPC `QSimAPI` и его сообщения. Итог — обзор структуры и безопасные правки.

## Сбор контекста
- [Факт] Сервис зависит от `sensor_raw_in.proto` и `actuator_raw_out.proto`.
- [Факт] Комментарии указывают на взаимодействие между Q-Core Agent и Q-Sim Service.
- [Гипотеза] Предполагается использование в симуляторе робота.

## Локализация артефакта
- [Факт] Путь: `QIKI_DTMP/protos/q_sim_api.proto`.
- [Факт] Вызывается через gRPC; версия `proto3`.

## Фактический разбор
- [Факт] Импорты: `sensor_raw_in.proto`, `actuator_raw_out.proto`, `google/protobuf/empty.proto`.
- [Факт] Сервис `QSimAPI` содержит методы `GetSensorData`, `SendActuatorCommand`, `HealthCheck`.
- [Факт] Сообщение `HealthResponse` имеет поля `status`, `message`, `timestamp`.
- [Гипотеза] Возможные статусы ограничены "OK"/"ERROR".

## Роль в системе и связи
- [Факт] Сервис предоставляет IPC между симулятором и агентом.
- [Гипотеза] Клиентом является `Q-Core Agent`, сервером — `Q-Sim Service`.

## Несоответствия и риски
- [Гипотеза][Med] Отсутствует enum для статуса, возможны опечатки.
- [Гипотеза][Low] Нет поля для кода ошибки в `HealthResponse`.

## Мини-патчи (safe-fix)
- [Патч] Ввести enum `HealthStatus` вместо строкового поля.
- [Патч] Добавить поле `int32 error_code = 4` для детализации.

## Рефактор-скетч
```proto
enum HealthStatus { OK = 0; ERROR = 1; }
message HealthResponse {
  HealthStatus status = 1;
  string message = 2;
  int64 timestamp = 3;
  int32 error_code = 4;
}
```

## Примеры использования
1. ```bash
python -m grpc_tools.protoc -I protos --python_out=. --grpc_python_out=. protos/q_sim_api.proto
```
2. ```python
import q_sim_api_pb2_grpc as api
channel = grpc.insecure_channel('localhost:50051')
stub = api.QSimAPIStub(channel)
```
3. ```python
from google.protobuf.empty_pb2 import Empty
resp = stub.GetSensorData(Empty())
```
4. ```python
cmd = actuators_pb2.ActuatorCommand(...)
stub.SendActuatorCommand(cmd)
```
5. ```python
health = stub.HealthCheck(Empty())
print(health.status)
```

## Тест-хуки/чек-лист
- Компиляция `protoc` без ошибок.
- Клиентские вызовы возвращают корректные типы.
- Проверка обработки недоступности сервиса.

## Вывод
Текущий протокол минимально покрывает обмен данными между агентом и симулятором. Немедленно стоит формализовать статус через enum и добавить код ошибки. Отложить расширение полей ответа до появления новых требований.
