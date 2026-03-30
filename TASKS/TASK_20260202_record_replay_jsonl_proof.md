# TASK: Record/Replay JSONL proof (Phase1, no-mocks)

**Date:** 2026-02-02  
**Goal:** Prove that we can record real `qiki.telemetry` + `qiki.events.v1.>` to a JSONL file and replay it back to NATS (without creating “v2” or parallel contracts).

## Canonical sources

- Recorder/replayer implementation: `src/qiki/shared/record_replay.py`
- Helper CLIs:
  - `tools/nats_record_jsonl.py`
  - `tools/nats_replay_jsonl.py`

## JSONL line format

Each line is a JSON object:

- `schema_version=1`
- `type`: `telemetry|event|unknown`
- `ts_epoch` (float seconds; from payload `ts_epoch` / `ts_unix_ms` when available)
- `subject` (original NATS subject)
- `data` (original decoded JSON payload or `{raw: ...}`)

## Integration proof

- `tests/integration/test_record_replay_jsonl.py`
  - records ~2s from `qiki.telemetry` and `qiki.events.v1.>` into a temp JSONL file
  - replays into prefix `replay.*`
  - asserts at least one replayed telemetry and one replayed event are received (skips if events are disabled)

## How to run (Docker-first)

- `./scripts/run_integration_tests_docker.sh tests/integration/test_record_replay_jsonl.py`

## Evidence (2026-02-02)

- `./scripts/run_integration_tests_docker.sh tests/integration/test_record_replay_jsonl.py` → pass

