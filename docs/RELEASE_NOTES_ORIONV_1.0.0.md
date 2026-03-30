# ORION V 1.0.0 — Release Notes

Date: 2026-02-26
Branch: `ORION`

## Summary

ORION V is now the production-default operator console for QIKI_DTMP pilot runtime.
Legacy ORION remains available only as an isolated fallback profile.

## Scope by stage

### Stage 2.5
- Ruff `E501` cleanup and formatting pass.
- Quality gate alignment for lint baseline.

### Stage 3
- ORION V skeleton introduced:
  - new entrypoint
  - modular package layout (`app`, `screens`, `widgets`)
  - compose overlay path for parallel launch with legacy.

### Stage 4
- Functional expansion and production-readiness building blocks:
  - subsystem module contract (`SubsystemModule`)
  - dynamic F2 systems modules (Power/Thermal/Comms/Docking)
  - Deep/Raw bounded events + filters + pagination
  - procedure engine (command sequences + audit)
  - replay support + trend views
  - runbook and deployment readiness docs.

### Stage 5
- Pilot stabilization and observability:
  - reconnect lifecycle (`Connected/Reconnecting/Lost`)
  - safe resubscribe behavior
  - operator audit streams (`actions/procedures/incidents`)
  - F6 Audit view and F7 System Health
  - replay guardrails (control disabled)
  - cutover simulation artifacts.

### Stage 6
- Cutover rehearsal and gate:
  - rehearsal dossier with commands/evidence
  - canonical subject proof for operator actions
  - docs sync for cutover/rollback/quickstart.

### Stage 7
- ORION V switched to default console entrypoint.
- Legacy isolation via `docker-compose.operator_legacy.yml` + `--profile legacy`.
- Short stability verification with reconnect + burst load.
- Final cutover status documented as `Executed`.

## Architecture highlights

- ORION V is the active runtime path for operator console.
- Legacy runtime is intentionally decoupled from default compose path.
- Canonical operator action events use:
  - `qiki.events.v1.operator.actions`

## Stability proof highlights

- repeated NATS restart recovery validated
- burst load validated (thousands of events)
- quality gate green at final cutover state.

## Cutover / rollback

See:
- `docs/CUTOVER_PLAN.md`
- `docs/ORION_V_RUNBOOK.md`
- `docs/ORION_V_QUICKSTART.md`
- `TASKS/TASK_stage7_primary_switch.md`
- `TASKS/TASK_stage7_final_cutover.md`
