# TASK: ORION V Stage 4 functional expansion and pilot readiness

Status: done

## Context

Stage 4 target: move ORION V from extended prototype to pilot-ready console while preserving legacy fallback.

## Scope

- 4.1: subsystem architecture expansion (Thermal/Comms/Docking + auto-discovery).
- 4.2: Deep/Raw filtering and pagination for high event flow.
- 4.3: command sequence engine (procedures) with ack waits and audit logging.
- 4.4: replay mode from JetStream history + basic trend output (SOC/Temperature/Voltage).
- 4.5: production docs (quickstart + runbook) and smoke guidance.

## Operator Scenario (visible outcome)

Operator opens ORION V and sees dynamic F2 subsystem list with status tags (`OK/WARN/CRIT`). In high event volume, F3/F4 remain responsive with filters and page navigation. Operator can launch a named procedure and monitor step progress/ack status. Replay mode allows reading historical events without breaking live mode. Runbook now covers start/restart/health/rollback and pilot smoke sequence.

## Reproduction Commands

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_orionv.yml up -d --build
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_orionv.yml ps
bash scripts/quality_gate_docker.sh
```

Incident smoke:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
import asyncio, json, nats
async def main():
    nc = await nats.connect("nats://nats:4222")
    await nc.publish("qiki.events.v1.audit", json.dumps({
        "incident_id":"pilot-inc-1","severity":"C","description":"pilot smoke incident"
    }).encode())
    await nc.flush()
    await nc.close()
asyncio.run(main())
PY
```

## Before / After

Before:
- F2 had only initial module slice and static module registry update path.
- F3/F4 rendered recent events without production filtering/pagination.
- No procedure engine and no replay mode.
- No dedicated Stage-4 runbook for pilot operations.

After:
- F2 auto-discovers subsystem modules (`power/thermal/comms/docking`) without core wiring changes.
- Each module returns summary/details/sources and handles missing telemetry with `N/A`.
- F3/F4 support `sev/subsys/range` filters + paging (`PgUp/PgDn`, commands).
- Procedure engine executes JSON/YAML sequences with ack timeouts and audit events.
- Replay mode loads JetStream event history and exposes trend summaries in F4 raw payload.
- Added `docs/ORION_V_RUNBOOK.md` and expanded `docs/ORION_V_QUICKSTART.md`.

## Impact Metric

- Extensibility: +3 new subsystem modules integrated with zero F2-core edits.
- Scalability: event rendering bounded to `ORIONV_EVENTS_PAGE_SIZE` page output.
- Operational control: deterministic procedure lifecycle (`start/step/failed/done`) with audit events.
- Historical analysis: replay toggle + trend summaries available in operator workflow.
- Deployment readiness: reproducible runbook with rollback and smoke scenario.

## Evidence

- Unit tests:
  - `tests/unit/test_orion_v_subsystem_modules.py`
  - `tests/unit/test_orion_v_events_store.py`
  - `tests/unit/test_orion_v_app_incidents.py`
  - `tests/unit/test_orion_v_procedure_engine.py`
- Lint:
  - `ruff check src/qiki/services/operator_console/orion_v src/qiki/services/operator_console/clients/nats_client.py tests/unit/test_orion_v_*.py`
- Docker quality gate:
  - `bash scripts/quality_gate_docker.sh` => `OK`.
- Runtime smoke:
  - ORION V container healthy in compose `ps`.
  - logs show `NATS: Connected`.
  - injected incident `pilot-inc-1` appears in `ALERTS (Level 0)` and `Active C/A 1`.
