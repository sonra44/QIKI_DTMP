# ORION V Cutover Plan

## Status

- `Execution status`: primary ORION V path is proven on the canonical Phase1/operator stack; current follow-up work is regression/hardening, not blocker recovery
- Intended primary console: ORION V
- Legacy mode: isolated (`docker-compose.operator_legacy.yml`, `--profile legacy`)

Current baseline note:
- This cutover plan is not a substitute for the narrower maintenance and regression source-of-truth docs for the current slice.
- Historical `M4` radar trust closure (`RadarTrackStore` LR/SR merge continuity) is already recorded with evidence in `TASKS/TASK_20260202_exec_plan_p0_sequential.md`.
- Treat ORION V primary status as the current canonical operating mode; remaining follow-up is maintenance-oriented reproducibility/regression proof.

## Goal

Run a controlled migration from legacy ORION to ORION V with reversible steps and documented rollback.

## One-Line Commands (copy/paste)

- Rehearsal start (`phase1 + operator + ORION V overlay`):
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build`
- Rehearsal stop:
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml down -v`
- Legacy-only stable start (rollback target):
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_legacy.yml --profile legacy up -d --build operator-console`
- Legacy-only stop:
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml stop operator-console`

Legacy mode is rollback/diagnostics only and is not allowed for production runtime.

## Cutover Modes

1. `legacy only`
2. `legacy + ORION V`
3. `ORION V only` (current canonical operator mode)

## Stage 6.1 Rehearsal DoD

1. ORION V container is healthy.
2. NATS is healthy and ORION V transitions `Connected -> Reconnecting -> Connected` on broker restart.
3. No subscription leak after reconnect (runtime + unit proof):
   - runtime: no crash loop and normal event flow after NATS restart and burst load;
   - unit: `tests/unit/test_orion_v_nats_client.py` covers replace/resubscribe without duplicate growth.
4. Audit stream proof for canonical operator subjects:
   - incident lifecycle (`incident_open/ack/clear`): `qiki.events.v1.operator.incidents`;
   - generic operator actions: `qiki.events.v1.operator.actions`.
5. Burst load (1000-3000 events) keeps stack stable and ORION V alive.

## Stage 6.2 Pilot Cutover Steps

1. Record rollback point:
   - stable legacy command above (`legacy-only stable start`).
2. Minimal downtime switch:
   - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
3. Validate:
   - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps`
   - `curl -s http://localhost:8222/healthz`
   - operator cycle: incident -> ack -> clear -> audit event on `qiki.events.v1.operator.incidents`
4. Validate acceptance:
   - F-levels `F1/F2/F3/F4/F6/F7`
   - procedures `proc list/run/status` in live
   - replay guardrail (`REPLAY MODE — CONTROL DISABLED`, no control actions)

## Stage 6.3 Final Gate Before Merge

1. `bash scripts/quality_gate_docker.sh`
2. Minimal smoke e2e:
   - stack start
   - publish incident
   - ack/clear
   - audit proof on canonical operator subjects (`...operator.actions` + `...operator.incidents`)
3. Subject canonicality check:
   - operator action events use `qiki.events.v1.operator.actions`;
   - incident lifecycle events use `qiki.events.v1.operator.incidents`.
4. Upstream gate check:
   - `M4` trust status is green, including LR/SR merge continuity evidence.

## Rollback (1-2 commands)

1. `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
2. `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_legacy.yml --profile legacy up -d --build operator-console`

## Evidence

- Stage 6 dossier: `TASKS/TASK_20260226_stage6_cutover_rehearsal.md`
- Stage 7 primary switch dossier: `TASKS/TASK_stage7_primary_switch.md`
- Stage 7 final cutover dossier: `TASKS/TASK_stage7_final_cutover.md`
