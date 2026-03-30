# TASK: ORION V Stage 5 pilot stabilization and cutover preparation

Status: done

## Context

Stage 5 target: stabilize ORION V for long-running pilot usage and prepare deterministic cutover with rollback.

## Scope

- 5.1.1 session stability: NATS reconnect states + safe auto-resubscribe + duplicate-subscription protection.
- 5.1.2 operator audit trail: split audit subjects (`actions/procedures/incidents`) and F6 Audit View.
- 5.1.3 resource/load monitoring: runtime metrics and F7 System Health.
- 5.1.4 replay guardrails: hard control blocking with explicit replay banner.
- 5.1.5 cutover simulation readiness: cutover plan/checklist + rollback steps.

## Operator Scenario (visible outcome)

Operator keeps ORION V open during broker restart: header transitions `Connected -> Reconnecting -> Connected` without UI crash or duplicate subscriptions. Operator actions (level switch, replay toggle, incident ack/clear, procedure lifecycle) appear in F6 audit trail. F7 shows live runtime metrics (events/s, queue depth, latencies, CPU/memory, active subscriptions). In replay mode, control actions are visibly and strictly blocked (`REPLAY MODE — CONTROL DISABLED`).

## Reproduction Commands

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_orionv.yml up -d --build
docker compose -f docker-compose.phase1.yml restart nats
docker logs --since=2m qiki-operator-console | rg "NATS: (Connected|Reconnecting|Lost)"
```

High-load publish (>3000):

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
import asyncio, json, nats
async def main():
    nc = await nats.connect("nats://nats:4222")
    for i in range(3200):
        await nc.publish("qiki.events.v1.audit", json.dumps({
            "incident_id": f"load-inc-{i}",
            "severity": "INFO" if i % 5 else "WARN",
            "description": f"load event {i}",
            "subsystem": "thermal" if i % 2 else "power",
            "ts_unix_ms": 1700000000000 + i,
        }).encode())
    await nc.flush()
    await nc.close()
asyncio.run(main())
PY
```

Quality gate:

```bash
bash scripts/quality_gate_docker.sh
```

## Before / After

Before:
- NATS in ORION V had only connected/disconnected boolean.
- No dedicated audit channels for action/procedure/incident.
- No F6/F7 operator views for audit and runtime health.
- Replay blocked incident controls only partially and did not hard-block procedures.
- Cutover sequence was scattered.

After:
- NATS lifecycle is explicit (`connected/reconnecting/lost`), reconnect resubscribes safely.
- Audit is centralized by subject split:
  - `qiki.events.v1.operator.actions`
  - `qiki.events.v1.operator.procedures`
  - `qiki.events.v1.operator.incidents`
- Added F6 Audit View with type filter + pagination.
- Added F7 System Health with live load/runtime metrics.
- Replay mode now displays hard banner and blocks all control actions (`ack/clear/proc run`).
- Added `docs/CUTOVER_PLAN.md` with dry-run and rollback checklist.

## Impact Metric

- Stability: broker restart recovers automatically; no duplicate-subscription explosion observed.
- Observability: operator actions become queryable by type and visible in F6.
- Performance control: >3000 event burst handled while container remains healthy.
- Safety: replay mode cannot mutate runtime state via control actions.
- Deployment readiness: explicit cutover plan and rollback path available.

## Evidence

- Unit tests:
  - `tests/unit/test_orion_v_app_incidents.py`
  - `tests/unit/test_orion_v_nats_client.py`
  - `tests/unit/test_orion_v_events_store.py`
  - `tests/unit/test_orion_v_procedure_engine.py`
  - `tests/unit/test_orion_v_subsystem_modules.py`
- Lint:
  - `ruff check src/qiki/services/operator_console/orion_v src/qiki/services/operator_console/clients/nats_client.py tests/unit/test_orion_v_app_incidents.py tests/unit/test_orion_v_nats_client.py`
- Quality gate:
  - `bash scripts/quality_gate_docker.sh` => `OK`
- Runtime smoke:
  - NATS restart shows `NATS: Reconnecting` then `NATS: Connected` in ORION V logs.
  - `published=3200` load burst executed; `operator-console` remains healthy in compose `ps`.
