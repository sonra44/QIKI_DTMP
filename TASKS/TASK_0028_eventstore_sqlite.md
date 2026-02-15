# TASK-0028 — EventStore Durable Storage v1 (SQLite)

## Status
- State: in_progress
- Scope: durable EventStore backend, retention, Trace/Replay integration

## What Changed
- Added durable backend support in `src/qiki/services/q_core_agent/core/event_store.py`:
  - `EVENTSTORE_BACKEND=memory|sqlite|hybrid`
  - Async SQLite writer with queue+batch (`EVENTSTORE_QUEUE_MAX`, `EVENTSTORE_BATCH_SIZE`, `EVENTSTORE_FLUSH_MS`)
  - SQLite schema + indexes:
    - `events(id, ts, subsystem, event_type, truth_state, session_id, payload_json, schema_version)`
    - indexes: `(ts)`, `(event_type, ts)`, `(subsystem, ts)`, `(session_id, ts)`
  - Unified API:
    - `append(event)`, `append_new(...)`
    - `query(from_ts, to_ts, types, subsystems, truth_states, limit, order)`
    - `stats()` and `close()`
  - Retention/compaction controls:
    - `EVENTSTORE_RETENTION_HOURS`
    - `EVENTSTORE_MAX_DB_MB`
    - `EVENTSTORE_VACUUM_ON_START=0|1` (default `0`)
  - Lifecycle events:
    - `EVENTSTORE_DB_OPENED`
    - `EVENTSTORE_DB_WRITE_LAG`
    - `EVENTSTORE_RETENTION_RUN`
    - `EVENTSTORE_DROP`

- Updated Trace export integration in `src/qiki/services/q_core_agent/core/trace_export.py`:
  - Export now reads from `EventStore.query(...)` so filters/time windows behave consistently on memory and SQLite.

- Updated Replay integration:
  - Added SQLite trace loader in `src/qiki/services/q_core_agent/core/radar_replay.py` (`load_trace_from_db`).
  - Added `RADAR_REPLAY_DB` path in `src/qiki/services/q_core_agent/core/radar_pipeline.py`.
  - Replay source selection:
    - `RADAR_REPLAY_FILE` (JSONL) has priority
    - then `RADAR_REPLAY_DB` (SQLite)

## ENV Knobs
- `EVENTSTORE_BACKEND=memory|sqlite|hybrid`
- `EVENTSTORE_DB_PATH=<path>`
- `EVENTSTORE_BATCH_SIZE=200`
- `EVENTSTORE_QUEUE_MAX=10000`
- `EVENTSTORE_FLUSH_MS=50`
- `EVENTSTORE_RETENTION_HOURS=24`
- `EVENTSTORE_MAX_DB_MB=512`
- `EVENTSTORE_VACUUM_ON_START=0|1`
- `EVENTSTORE_STRICT=0|1`
- `RADAR_REPLAY_DB=<path-to-sqlite>`

## Maintenance Notes
- Retention deletes old rows in batches (no VACUUM in hot loop).
- VACUUM runs only on explicit startup flag (`EVENTSTORE_VACUUM_ON_START=1`).

## Validation Plan
- Unit:
  - roundtrip append/query payload integrity
  - query filters (time/type/subsystem/limit)
  - retention removes stale rows
- Integration:
  - pipeline writes `RADAR_RENDER_TICK` into SQLite
  - trace export from SQLite backend
  - replay from SQLite source (`RADAR_REPLAY_DB`)
