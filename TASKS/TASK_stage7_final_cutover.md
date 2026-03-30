# TASK: Stage 7.4 + 7.5 — Final cutover execution and release preparation

## Status

- `done` (2026-02-26)

## Stage 7.4 — Final cutover execution

### Execution date

- 2026-02-26

### Cutover state

- Default console: ORION V (`main_orion_v.py`)
- Legacy runtime: isolated (`docker-compose.operator_legacy.yml`, `--profile legacy`)
- Health baseline:
  - `curl -s http://localhost:8222/healthz` -> `{"status":"ok"}`
  - `docker compose ... ps` -> core services `Up`, key services healthy

### Validation highlights

- ORION V header shows `NATS: Connected`
- Reconnect rehearsal performed with repeated broker restarts
- Burst event load processed without container crash
- Quality gate passed after final fixes

### Documentation updated

- `docs/CUTOVER_PLAN.md`:
  - status marked `Executed` with date
  - default/rollback commands updated
- `docs/ORION_V_RUNBOOK.md`:
  - ORION V as default runtime
  - rollback path via legacy profile
- `docs/ORION_V_QUICKSTART.md`:
  - default ORION V run path
  - legacy fallback path isolated

## Stage 7.5 — Release and tag

### Completed actions in this task

1. Stage 7 changes committed to branch `ORION`: `38e1fc2`.
2. Branch pushed to `origin/ORION`.
3. Release tag created: `orionv-1.0.0`.
4. Tag pushed to origin.
5. Release notes prepared: `docs/RELEASE_NOTES_ORIONV_1.0.0.md`.

### Notes on PR merge

- Direct merge `ORION -> main` is repository/governance action and may require manual review/approval.
- This task prepares branch, tag, and release notes content from the engineering side.

## DoD mapping

- CUTOVER_PLAN status is `Executed`: `yes`
- Cutover date recorded: `yes`
- Default ORION V confirmed: `yes`
- Legacy excluded from default runtime: `yes`
- Health + reconnect baseline confirmed: `yes`
- Final tag creation/push: `yes`
