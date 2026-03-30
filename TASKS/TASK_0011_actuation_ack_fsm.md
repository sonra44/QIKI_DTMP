# TASK-0011 — ActuationResult -> FSM (ACCEPTED != EXECUTED)

## Как было (unsafe)
- FSM переходы в `ship_fsm_handler.py` опирались на `propulsion_mode`.
- `propulsion_mode` обновлялся уже на `ActuationStatus.ACCEPTED` в `ShipActuatorController`.
- Это позволяло перейти в полётные состояния без факта исполнения (`EXECUTED`).

## Карта команда -> ожидаемый FSM-эффект
- `set_main_drive_thrust_result(...)`
  - Ожидаемый эффект FSM: `SHIP_IDLE -> FLIGHT_CRUISE` (или `FLIGHT_MANEUVERING -> FLIGHT_CRUISE`) только при `EXECUTED`.
  - При `ACCEPTED`: состояние не меняется, фиксируется pending-статус.
- `fire_rcs_thruster_result(...)`
  - Ожидаемый эффект FSM: `SHIP_IDLE -> FLIGHT_MANEUVERING` (или `FLIGHT_CRUISE -> FLIGHT_MANEUVERING`) только при `EXECUTED`.
  - При `ACCEPTED`: состояние не меняется, фиксируется pending-статус.

## Как стало (truthful)
- Введён контракт квитанции `LastActuation` в `ship_fsm_handler.py` и синхронизация в `context_data`:
  - `last_actuation_command_id`
  - `last_actuation_status`
  - `last_actuation_timestamp`
  - `last_actuation_reason`
  - `last_actuation_is_fallback`
  - `last_actuation_action`
- `ship_actuators.py` теперь хранит последнюю квитанцию с `action/timestamp` и отдаёт её через `get_last_actuation()`.
- FSM-гейты:
  - `EXECUTED` -> разрешён переход
  - `ACCEPTED` -> только pending (без перехода)
  - `TIMEOUT/UNAVAILABLE/FAILED` -> вход в `SAFE_MODE` с `ACTUATOR_UNAVAILABLE`
  - `REJECTED` -> переход запрещён, остаёмся в текущем состоянии

## Примечание по контракту
- Если execution-ack недоступен (система выдаёт только `ACCEPTED`), FSM работает в accepted-only режиме честно: переходы, требующие исполнения, не выполняются.