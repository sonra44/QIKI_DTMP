# Отчёт: `generated/q_sim_api_pb2_grpc.py`

## Вход и цель
- [Факт] Анализ gRPC-сервиса `QSimAPI` в `generated/q_sim_api_pb2_grpc.py`.
- [Факт] Итог: обзор клиентского и серверного API.

## Сбор контекста
- [Факт] Файл сгенерирован из `q_sim_api.proto` и зависит от `actuator_raw_out_pb2`, `sensor_raw_in_pb2`, `q_sim_api_pb2`, `empty_pb2`.
- [Гипотеза] Используется для связи Q-Core Agent с симулятором.

## Локализация артефакта
- [Факт] Путь: `generated/q_sim_api_pb2_grpc.py` (архив `QIKI_DTMP.zip`).
- [Факт] Требует `grpcio >= 1.74.0` и пакеты `protobuf`.

## Фактический разбор
- [Факт] `QSimAPIStub` реализует методы `GetSensorData`, `SendActuatorCommand`, `HealthCheck`.
- [Факт] `QSimAPIServicer` определяет заглушки тех же методов, возвращающие `UNIMPLEMENTED`.
- [Факт] `add_QSimAPIServicer_to_server` регистрирует RPC-хэндлеры на сервере.
- [Факт] Класс `QSimAPI` предоставляет экспериментальный вызов без канала.
- [Гипотеза] Все методы работают в режиме unary-unary без стриминга.

## Роль в системе и связи
- [Факт] Обеспечивает RPC-взаимодействие между агентом и симулятором.
- [Гипотеза] Может быть расширен стриминговыми методами для потоковых данных.

## Несоответствия и риски
- [Факт] Методы сервиса не реализованы (High).
- [Гипотеза] Отсутствие таймаутов и ретраев в клиентском stub (Med).

## Мини-патчи (safe-fix)
- [Патч] Реализовать минимальные заглушки в `QSimAPIServicer`, возвращающие осмысленные ошибки.
- [Патч] Добавить параметры таймаута при вызове методов stub.

## Рефактор-скетч (по желанию)
```python
# [Патч]
class QSimAPIServicer(q_sim_api_pb2_grpc.QSimAPIServicer):
    def HealthCheck(self, request, context):
        return q_sim_api_pb2.HealthResponse(status="OK")
```

## Примеры использования
```python
# [Факт] Клиент
stub = q_sim_api_pb2_grpc.QSimAPIStub(channel)
resp = stub.HealthCheck(empty_pb2.Empty())

# [Факт] Сервер
servicer = q_sim_api_pb2_grpc.QSimAPIServicer()
q_sim_api_pb2_grpc.add_QSimAPIServicer_to_server(servicer, server)
```

## Тест-хуки/чек-лист
- [Факт] Unit-тест регистрации сервиса через `add_QSimAPIServicer_to_server`.
- [Гипотеза] Интеграционный тест обмена данными сенсоров и актуаторов.

## Вывод
- [Факт] Сервис описан, но методы не реализованы.
- [Патч] Реализовать методы и добавить таймауты клиента.
- [Гипотеза] Стриминговые вызовы можно внедрить позже.
