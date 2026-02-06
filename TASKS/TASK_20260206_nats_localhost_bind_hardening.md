# TASK: Phase1 NATS localhost bind hardening

Date: 2026-02-06

## Goal
Reduce Phase1 control-plane exposure without changing runtime semantics:
- keep inter-container connectivity (`nats://nats:4222`)
- restrict host-exposed NATS ports to loopback only

## Change
- Updated `docker-compose.phase1.yml`:
  - `4222:4222` -> `127.0.0.1:4222:4222`
  - `8222:8222` -> `127.0.0.1:8222:8222`

## Verification (evidence)
1. Recreate NATS:
   - `docker compose -f docker-compose.phase1.yml up -d --force-recreate nats`
2. Service/ports:
   - `docker compose -f docker-compose.phase1.yml ps nats`
   - shows `127.0.0.1:4222->4222` and `127.0.0.1:8222->8222`
   - `docker port qiki-nats-phase1` confirms loopback host IP bindings
3. Host health:
   - `curl -sf http://127.0.0.1:8222/healthz` -> `{"status":"ok"}`
4. Container connectivity preserved:
   - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY' ... socket.create_connection(("nats", 4222)) ... PY`
   - output: `OK: qiki-dev TCP -> nats:4222`
5. Regression gate:
   - `bash scripts/quality_gate_docker.sh` -> `[quality-gate] OK`

## Result
- Exposure footprint reduced for Phase1 host access.
- No functional regressions observed in current quality gate/smokes.

