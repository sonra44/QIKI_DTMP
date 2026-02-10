# TASK-0002 — gRPC Data Provider: explicit truth absence (no silent fallback)

Date: 2026-02-10  
Scope: `src/qiki/services/q_core_agent/core/grpc_data_provider.py` only (+ unit tests)

## Как было
- RPC: `QSimAPIServiceStub.GetSensorData(...)` in `GrpcDataProvider.get_sensor_data()`.
- Ошибки `grpc.RpcError` ловились и превращались в синтетический `SensorData(sensor_type=OTHER, scalar_data=0.0)`.
- На верхний уровень уходил объект, похожий на валидный факт, хотя truth из gRPC не получен.

## Почему это подмена truth
- Ошибка транспорта (`timeout/unavailable`) семантически равна отсутствию факта.
- Подставленный `scalar_data=0.0` может быть интерпретирован downstream как реальное измерение.
- Терялся причинный факт: данные недоступны из-за RPC ошибки.

## Какой факт терялся
- Причина отсутствия truth (`timeout`, `unavailable`, `invalid payload`).
- Разделение состояний `OK(data)` vs `NoData(error-reason)`.

## Изменения
- Введены специализированные ошибки:
  - `GrpcDataUnavailable`
  - `GrpcTimeout`
  - `GrpcInvalidPayload`
- Дефолтная политика: `QIKI_ALLOW_GRPC_FALLBACK=false` (по умолчанию) -> fail-fast исключение, без синтетических чисел.
- Стендовый режим: `QIKI_ALLOW_GRPC_FALLBACK=true` -> возвращается явно маркированный fallback payload:
  - `string_data="NO_DATA"`
  - `metadata.is_fallback=true`
  - `metadata.reason=<timeout|unavailable|invalid_payload>`
  - `quality_score=0.0`
- Добавлена минимальная валидация payload:
  - обязательный `reading.sensor_id.value`
  - ошибки конвертации считаются `invalid payload` (не truth)

## Тесты
- `timeout/unavailable` (fallback disabled) -> `GrpcTimeout`/`GrpcDataUnavailable`.
- `invalid payload` (fallback disabled) -> `GrpcInvalidPayload`.
- `happy path` -> валидный `SensorData`.
- Дополнительно: fallback enabled -> явный маркированный `NO_DATA`.

Файл тестов: `src/qiki/services/q_core_agent/tests/test_grpc_data_provider_truth_absence.py`

## Repro script (timeout local)
```bash
cd /home/sonra44/QIKI_DTMP
QIKI_ALLOW_GRPC_FALLBACK=false pytest -q src/qiki/services/q_core_agent/tests/test_grpc_data_provider_truth_absence.py -k timeout
```
