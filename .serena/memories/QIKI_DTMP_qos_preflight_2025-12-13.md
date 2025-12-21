# QIKI_DTMP — QoS preflight cleanup (2025-12-13)

## Goal of this handover
Before starting QoS interfaces, the repo was cleaned up to reduce drift in NATS subjects, ensure JetStream durable consumption is explicit, and avoid entrypoint-import / sys.path hacks.

## What changed
- Canonical NATS subjects/stream names added: `src/qiki/shared/nats_subjects.py`.
- FastStream bridge (`src/qiki/services/faststream_bridge/app.py`): radar frames subscriber now uses JetStream durable consumer via `durable=RADAR_FRAMES_DURABLE` + `stream=RADAR_STREAM`.
- QSimService moved out of entrypoint:
  - new: `src/qiki/services/q_sim_service/service.py`
  - entrypoint: `src/qiki/services/q_sim_service/main.py` now thin
  - gRPC server updated: `src/qiki/services/q_sim_service/grpc_server.py` imports from `service.py` and no longer uses sys.path hacks.
- q_core_agent entrypoint updated to avoid sys.path hacks and import QSimService from `service.py`: `src/qiki/services/q_core_agent/main.py`.
- Registrar entrypoint refactored:
  - `src/qiki/services/registrar/main.py` no sys.path setup
  - subscribes to `qiki.radar.v1.frames` and `qiki.events.v1.>` with JetStream `stream+durable`
  - publishes audit records to `qiki.events.v1.audit` with CloudEvents headers.
- JetStream initializer enhanced:
  - `tools/js_init.py` now optionally creates `QIKI_EVENTS_V1` stream + audit consumer when `EVENTS_ENABLED=1`.
  - Compose env updated: `docker-compose.yml`, `docker-compose.phase1.yml`, `docker-compose.minimal.yml`.
- Test discipline:
  - `tests/conftest.py` auto-marks `tests/integration/*` as `integration`.
  - `pytest.ini` excludes integration by default: `addopts = -q -m "not integration"`.
  - NATS integration tests use `connect_timeout=1` and skip if no server.

## Verification
- `pytest` (default, without integration) -> `57 passed, 2 skipped, 5 deselected`.

## Next step (QoS interfaces)
- Decide QoS scope: JetStream consumer config (ack_wait/max_deliver/max_ack_pending/durable), publish policies, and gRPC timeouts/retries.
- Design API: QoS enum/classes (e.g. control/telemetry/bulk/science) + mapping to JetStream configs and per-subject defaults.
- Apply in: faststream_bridge consumers/publishers, operator_console subscriptions, registrar audit stream.

## Notes
- Sovereign-memory also has episodic STATUS/TODO for 2025-12-13 and core rules: `topic=import-policy`, `topic=SERENA`, `topic=work-principles`.