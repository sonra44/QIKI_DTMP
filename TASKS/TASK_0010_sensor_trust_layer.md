# TASK-0010 — Sensor Trust Layer

## Как было
- В `src/qiki/services/q_core_agent/core/ship_fsm_handler.py` валидация сенсоров была локальной (`SensorValidityResult`) и фактически привязана к docking.
- FSM читал raw track через `_get_best_station_track()` в нескольких местах (`is_docking_target_in_range`, `is_docking_engaged`) и сам решал, что считать валидным.
- Единый контракт `ok/reason/age/quality/data` отсутствовал, поэтому повторение проверок было неизбежно.

## Как стало
- Введён единый контракт доверия:
  - `SensorTrustReason`: `OK | NO_DATA | STALE | LOW_QUALITY | INVALID | MISSING_FIELDS`.
  - `TrustedSensorFrame`: `ok`, `reason`, `age_s`, `quality`, `data`, `is_fallback`.
- Добавлена единая оценка доверия: `ShipContext.evaluate_sensor_frame(raw_frame) -> TrustedSensorFrame`.
- Добавлен контекстный метод `ShipContext.get_trusted_station_track() -> TrustedSensorFrame`.
- FSM-пути docking переведены на trusted frame:
  - `is_docking_target_in_range()` использует только trusted данные.
  - `is_docking_engaged()` использует trusted данные и не читает raw напрямую.
- Сохранена backward-compat обёртка `validate_station_track()` (возвращает trusted frame) для минимального влияния на существующий код.

## Env knobs
- `QIKI_SENSOR_MAX_AGE_S` (default `2.0`) — максимальная допустимая «свежесть».
- `QIKI_SENSOR_MIN_QUALITY` (default `0.5`) — минимально допустимое качество.
- `QIKI_DOCKING_CONFIRMATION_COUNT` (default `3`) — подтверждение стыковки N подряд.

## Проверка
- Добавлен тестовый файл: `src/qiki/services/q_core_agent/tests/test_sensor_trust_layer.py`.
- Покрыты причины: `NO_DATA`, `STALE`, `LOW_QUALITY`, `INVALID`, `OK`.
- Добавлен regression-тест: FSM не переходит в docking по raw, если trusted frame вернул `ok=False`.
