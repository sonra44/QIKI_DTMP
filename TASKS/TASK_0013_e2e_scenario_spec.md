# TASK-0013 — E2E Ship->FSM->Actuators->Sensors->EventStore (BOOT→DOCKING_ENGAGED)

## Цель
Один воспроизводимый сквозной сценарий, подтверждающий, что контур работает как единая truth-система:
- FSM переходы;
- actuation receipts влияют на FSM (ACCEPTED != EXECUTED);
- sensor trust layer участвует в docking;
- EventStore хранит структурированный след;
- SAFE_MODE не срабатывает в happy path.

## Точка запуска (текущий проектный контур)
1. Создаётся `EventStore` (пассивный журнал фактов).
2. Создаётся `ShipActuatorController` с общим `EventStore`.
3. Создаётся `ShipFSMHandler` с тем же `EventStore`.
4. Цикл: `state = handler.process_fsm_state(state)`; между тиками подаются:
   - факты от актуаторов (`last_actuation` через result-first методы),
   - сенсорные чтения (station track) для trust/evaluate path.

## Сценарий TASK-0013 (один, детерминированный)
`SHIP_STARTUP -> SHIP_IDLE -> FLIGHT_MANEUVERING -> DOCKING_APPROACH -> DOCKING_ENGAGED`

Дополнительно в сценарий включён шаг проверки актации:
- `set_main_drive_thrust_result` со статусом `ACCEPTED` удерживает FSM в `SHIP_IDLE` (pending).
- `fire_rcs_thruster_result` со статусом `EXECUTED` разрешает переход в `FLIGHT_MANEUVERING`.

Далее:
- в `FLIGHT_MANEUVERING` подаётся station track в допустимом диапазоне (`docking target in range`),
  что переводит в `DOCKING_APPROACH`;
- в `DOCKING_APPROACH` подаются `N` последовательных валидных engaged-track показаний,
  после чего FSM переходит в `DOCKING_ENGAGED`.

## Детерминированные входы
- `QIKI_DOCKING_CONFIRMATION_COUNT=3`
- `QIKI_SENSOR_MAX_AGE_S=2.0`
- `QIKI_SENSOR_MIN_QUALITY=0.5`
- Все track timestamp свежие, quality >= 0.9.

## Проверки в e2e-тесте
- финальное состояние: `DOCKING_ENGAGED`;
- нет входа в `SAFE_MODE`;
- в EventStore есть:
  - `FSM_TRANSITION`,
  - `ACTUATION_RECEIPT` (`accepted` и `executed`),
  - `SENSOR_TRUST_VERDICT` с `reason=OK`;
- event trace экспортируется в JSONL (`.../artifacts/e2e_task_0013_events.jsonl`).

## Docker-first запуск
```bash
docker compose -f docker-compose.phase1.yml run --rm qiki-dev \
  pytest -q src/qiki/services/q_core_agent/tests/test_e2e_boot_idle_docking.py
```
