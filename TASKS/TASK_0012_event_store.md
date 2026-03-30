# TASK-0012 — Event Store (truth journal)

## Зачем
- После TASK-0001..0011 truth-контракты стали честными, но факты жили в моменте.
- Нужен единый детерминированный след событий для воспроизведения/отладки/дальнейшего UI.
- Event Store реализован как журнал фактов, а не источник принятия решений.

## Event schema
- `event_id`: UUID
- `ts`: unix timestamp
- `subsystem`: `FSM | SAFE_MODE | ACTUATORS | SENSORS | AGENT`
- `event_type`: тип события
- `payload`: структурированный dict
- `tick_id`: optional
- `truth_state`: `OK | NO_DATA | FALLBACK | INVALID`
- `reason`: строковый код причины

## Что реализовано
- Новый модуль: `src/qiki/services/q_core_agent/core/event_store.py`
  - `SystemEvent`
  - `EventStore` (in-memory ring buffer)
  - API: `append`, `append_new`, `recent`, `filter`, `export_jsonl`
  - Env knobs:
    - `QIKI_EVENT_STORE_MAXLEN` (default `1000`)
    - `QIKI_EVENT_STORE_ENABLE` (default `true`)

## Интеграция по подсистемам
- `ship_fsm_handler.py`
  - Запись `FSM_TRANSITION` (from/to/trigger/status/context snapshot)
  - Запись `SAFE_MODE` (enter/hold/recovering/exit, reason, exit_hits, confirmation_count)
  - Запись `SENSOR_TRUST_VERDICT` (ok/reason/age_s/quality/is_fallback)
- `ship_actuators.py`
  - Запись `ACTUATION_RECEIPT` на каждый `ActuationResult`
  - Поля: `action/status/command_id/correlation_id/reason/is_fallback/timestamp`
- `agent.py`
  - Запись `SAFE_MODE_REQUEST` при инициировании safe mode
  - Запись `DECISION_BLOCKED` когда команды блокируются из-за SAFE_MODE

## Как читать
- `event_store.recent(n)` — последние события в порядке записи.
- `event_store.filter(subsystem=..., event_type=...)` — точечная выборка.
- `event_store.export_jsonl(path)` — выгрузка на диск для офлайн-анализа.

## Инвариант
- Event Store не меняет FSM/агент бизнес-логику.
- Он только фиксирует уже принятые факты и их причины.
