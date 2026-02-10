# TASK-0008 — Ship FSM docking validation hardening

## Target
- `src/qiki/services/q_core_agent/core/ship_fsm_handler.py`

## Как было
- `DOCKING_APPROACH -> DOCKING_ENGAGED` срабатывал по одному тику, если `range_m <= engaged_range_m` и `abs(vr_mps) <= max_abs_vr_mps`.
- Не было явного контракта валидности сенсорного трека (`stale`, `low_quality`, `invalid`).
- Не было требования последовательного подтверждения (устойчивости) перед переходом в `DOCKING_ENGAGED`.

## Почему unsafe
- Один удачный/шумный тик мог привести к ложной стыковке.
- Устаревшие или низкокачественные данные не были явным стоп-фактором.
- Отсутствовал прозрачный контур причин: где проверка валидности провалилась и на каком шаге подтверждения мы находимся.

## Как стало
- Добавлен контракт валидности: `SensorValidityResult(ok, reason)` с причинами:
  - `NO_READINGS`
  - `STALE`
  - `MISSING_FIELDS`
  - `LOW_QUALITY`
  - `INVALID_VALUES`
- Добавлена валидация station-track перед docking decision:
  - `range_m > 0`
  - `vr_mps` конечное число
  - fresh-check через timestamp/age (`QIKI_SENSOR_MAX_AGE_S`)
  - quality-check (`QIKI_SENSOR_MIN_QUALITY`)
- `DOCKING_ENGAGED` теперь требует `N` последовательных подтверждений:
  - `QIKI_DOCKING_CONFIRMATION_COUNT` (default `3`)
  - счётчик хранится в `context_data["docking_confirm_hits"]`
  - при невалидном тике счётчик сбрасывается
- Триггеры в `DOCKING_APPROACH` сделаны явными:
  - `DOCKING_SENSOR_VALIDATION_FAILED`
  - `DOCKING_CONFIRMING_<k>_OF_<N>`
  - `DOCKING_CONFIRMED`

## Env knobs
- `QIKI_SENSOR_MAX_AGE_S` (default `2.0`)
- `QIKI_SENSOR_MIN_QUALITY` (default `0.5`)
- `QIKI_DOCKING_CONFIRMATION_COUNT` (default `3`)
- `QIKI_DOCKING_ENGAGED_RANGE_M` (existing)
- `QIKI_DOCKING_MAX_ABS_VR_MPS` (existing)

## Тесты
- `src/qiki/services/q_core_agent/tests/test_ship_fsm_docking_validation.py`
  - happy path: подтверждение только после 3 последовательных валидных тиков
  - no data / target lost
  - stale track
  - invalid values
  - flapping with counter reset
