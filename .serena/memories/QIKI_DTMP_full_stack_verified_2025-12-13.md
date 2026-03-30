# QIKI_DTMP — Full stack verified (2025-12-13)

## Summary
Full Phase1 stack + operator overlay was brought up and validated end-to-end with healthchecks and tests. Real runtime issues were discovered and fixed, then validation re-run.

## How to start
`docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build`

## Healthchecks
- NATS: `curl -sf http://localhost:8222/healthz` -> {"status":"ok"}
- Loki: `curl -sf http://localhost:3100/ready` -> ready
- Grafana: `curl -sf http://localhost:3000/api/health` -> database ok
- `docker compose ... ps` shows nats/q-sim-service healthy.

## Issues found + fixes
1) qiki-dev crash: `ModuleNotFoundError: common_types_pb2`
- Root cause: `PYTHONPATH` missing `/workspace/generated` in some compose files.
- Fix: `docker-compose.phase1.yml` + `docker-compose.minimal.yml` -> `PYTHONPATH=/workspace/src:/workspace:/workspace/generated` for `qiki-dev`.

2) faststream-bridge JetStream durable bind error: `TypeError: config.deliver_subject is required`
- Fix: `src/qiki/services/faststream_bridge/app.py` subscriber uses `pull_sub=True` with `durable`+`stream`.

3) registrar couldn't connect to NATS
- Root cause: default NATS_URL was localhost.
- Fix: `src/qiki/services/registrar/main.py` default `NATS_URL=nats://qiki-nats-phase1:4222`.

4) registrar audit loop via `qiki.events.v1.>`
- Fix: guard to ignore registrar’s own audit records.

5) qiki-dev container tests failing due to missing `textual`
- Fix: `requirements-dev.txt` includes `textual>=0.60.0`.

## Verification
- Host integration tests: `pytest -o addopts='' -m integration -q` -> 5 passed.
- Inside container `qiki-dev`:
  - `pytest -q` passes.
  - `pytest -o addopts='' -m integration -q` with `NATS_URL=nats://qiki-nats-phase1:4222` -> 5 passed.
- JetStream streams present and accumulating messages: `QIKI_RADAR_V1`, `QIKI_EVENTS_V1`.

## Stop
`docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml down`
