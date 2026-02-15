# TASK-0029 — Contracts & Release Hardening (stable core)

## Scope
- Frozen export envelope contract with `EVENT_SCHEMA_VERSION=1`.
- Unified strict mode via `QIKI_STRICT_MODE` (legacy strict flags work as aliases).
- Contract validation before SQLite durable write and JSONL export.
- Deterministic replay regression guard and time-call guard for deterministic radar core.
- Production plugin profile available in `plugins.yaml`.

## Event/Trace Contract
- Canonical envelope keys:
  - `schema_version`
  - `ts`
  - `subsystem`
  - `event_type`
  - `truth_state`
  - `reason`
  - `payload`
  - `session_id`
- `schema_version` is fixed to `1` in this task.
- Any future format change must bump `EVENT_SCHEMA_VERSION`.

## Strict Mode Matrix
- Global switch: `QIKI_STRICT_MODE=1|0`.
- Aliases kept for compatibility:
  - `QIKI_PLUGINS_STRICT`
  - `RADAR_POLICY_STRICT`
  - `EVENTSTORE_STRICT`
  - `RADAR_REPLAY_STRICT_DETERMINISM`
- Resolution order:
  1. `QIKI_STRICT_MODE` (if set)
  2. subsystem legacy alias
  3. subsystem default

## Non-Strict Fallback Visibility
- Plugins: `PLUGIN_FALLBACK_USED`.
- Policy loader path in pipeline: `POLICY_FALLBACK_USED`.
- Trace export invalid envelope/schema in non-strict: `TRACE_EXPORT_FALLBACK_USED`.
- EventStore invalid envelope in non-strict: `EVENTSTORE_DROP` with `INVALID_ENVELOPE`.

## Production Profile
- Added `production` profile in `src/qiki/resources/plugins.yaml`.
- Same built-in plugin chain as `prod`, now with explicit canonical profile name for release automation.

## Deterministic Guards
- Golden replay regression test asserts:
  - fused track signature stability,
  - situation event sequence stability (`event_type + track_id`),
  - stable telemetry invariants (`targets_count/lod_level/degradation_level/truth_state`).
- Core guard test asserts no direct `time.sleep()` / `time.time()` in deterministic radar core modules:
  - `radar_pipeline.py`
  - `radar_replay.py`
  - `radar_fusion.py`
  - `radar_situation_engine.py`
  - `radar_policy_loader.py`

## Verification Commands
```bash
docker compose -f docker-compose.phase1.yml run --rm qiki-dev pytest -q \
  src/qiki/services/q_core_agent/tests/test_runtime_contracts.py \
  src/qiki/services/q_core_agent/tests/test_core_time_guards.py \
  src/qiki/services/q_core_agent/tests/test_event_store_sqlite.py \
  src/qiki/services/q_core_agent/tests/test_trace_export.py \
  src/qiki/services/q_core_agent/tests/test_radar_replay.py \
  src/qiki/services/q_core_agent/tests/test_plugin_manager.py \
  src/qiki/services/q_core_agent/tests/test_radar_policy_loader.py \
  src/qiki/services/q_core_agent/tests/test_radar_pipeline.py
```
