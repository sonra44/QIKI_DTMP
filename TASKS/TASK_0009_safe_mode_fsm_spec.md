# TASK-0009 — SAFE_MODE as First-Class FSM State

## Как было
- `SAFE_MODE` не был самостоятельным состоянием в `ship_fsm_handler`.
- В `agent.py` `_switch_to_safe_mode()` только писал лог, без формального FSM-перехода и без обязательной причины.
- Не было единых правил удержания/выхода из safe режима, не было счётчика подтверждений выхода.
- Активные решения могли генерироваться без явного запрета при safe-сценариях.

## Почему это unsafe
- Невозможно формально доказать, почему система в safe режиме.
- Невозможно детерминированно выйти из safe режима.
- Нет жёсткой границы между “ошибка truth” и “обычная FSM-реакция”.

## Как стало
- Введено состояние `SAFE_MODE` в `ShipState`.
- Введён обязательный reason-контракт:
  - `BIOS_UNAVAILABLE`, `BIOS_INVALID`, `SENSORS_UNAVAILABLE`, `SENSORS_STALE`,
    `ACTUATOR_UNAVAILABLE`, `PROVIDER_UNAVAILABLE`, `UNKNOWN`.
- Вход в `SAFE_MODE` возможен из любого состояния через `safe_mode_request_reason`
  или через критичные truth-gates (`safe_bios_ok/safe_sensors_ok/safe_provider_ok`).
- В `SAFE_MODE` реализованы строгие exit-gates с подтверждением:
  - `QIKI_SAFE_EXIT_CONFIRMATION_COUNT` (default `3`)
  - счётчик `safe_mode_exit_hits` в `context_data`
  - при любом провале счётчик сбрасывается.
- `agent.py` больше не использует “голый safe flag”:
  - `_switch_to_safe_mode(reason=...)` инициирует FSM-запрос на переход.
  - активные actuator-команды блокируются, если FSM уже в `SAFE_MODE`.

## Env knobs
- `QIKI_SAFE_EXIT_CONFIRMATION_COUNT` (default `3`)

