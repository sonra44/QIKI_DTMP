# TASK: ORION V levels + overlay + bounded events

Status: done

## Context

Implement ORION V stage in parallel with legacy ORION: F1-F4 navigation, alerts overlay, Cockpit Tier-A summary, bounded events store, plus next slice with subsystem modules and incident ack/clear workflow.

## Scope

- ORION V app navigation and command routing (`f1..f4`, `help`, `q`).
- New F2/F3/F4 screens plus upgraded F1 cockpit summary.
- Level-0 alerts overlay for active C/A incidents.
- Bounded events store via env configuration.
- Subsystem module contract + first `Power` module and dynamic F2 systems rendering.
- Incident selection + `ack/clear` actions with confirmation dialogs in overlay/F3 workflow.
- Quickstart update with environment controls.

## Operator Scenario (visible outcome)

Operator starts ORION V through compose overlay and can switch between F1/F2/F3/F4. When C/A incidents appear in events stream, top overlay warns immediately with incident IDs/descriptions. Operator can select incidents and run `ack/clear` with confirm dialogs. Deep/Raw views show only last N events without overflowing UI.

## Reproduction Command

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_orionv.yml up -d --build
bash scripts/quality_gate_docker.sh
```

## Before / After

Before:
- ORION V was a minimal shell with only static cockpit + NATS status.
- No F1-F4 levels, no help command routing, no alerts overlay.
- No bounded events store for Deep/Raw.
- No subsystem module contract in F2.
- No incident acknowledgement/clear workflow in ORION V.

After:
- F1-F4 levels available via function keys and typed commands.
- Alerts overlay appears on active C/A incidents.
- Cockpit shows Tier-A summary from real telemetry/events with `N/A/—` fallback.
- Deep/Raw consume bounded store controlled by `ORIONV_MAX_EVENTS` and `ORIONV_EVENTS_PREVIEW`.
- F2 uses pluggable module contract (`SubsystemModule`) and renders `Power` module summary/details from telemetry.
- Overlay/F3 support incident selection and confirmed `ack/clear` actions.

## Impact Metric

- Navigation coverage: 4 operator levels (F1-F4) available in a single runtime.
- Event retention bounded deterministically to `ORIONV_MAX_EVENTS` (default 500) instead of unbounded growth.
- Overlay visibility metric: active C/A incidents are visible across all levels (0 hidden incidents when present in preview set).
- Incident action safety metric: all destructive incident actions (`ack`, `clear`) pass through explicit confirm dialog.
- Extensibility metric: new subsystem panels can be added via module registration without changing core app routing.

## Evidence

- `bash scripts/quality_gate_docker.sh` => `OK`.
- ORION V smoke:
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_orionv.yml up -d --build operator-console`
  - Logs show header `ORION V ... NATS: Connected` and Tier-A lines.
- Overlay incident smoke:
  - published `incident_id=orionv-stage-next-1` on `qiki.events.v1.audit`;
  - logs show `ALERTS (Level 0)` + `orionv-stage-next-1` + `Active C/A 1`.
- Legacy regression smoke:
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
  - logs show `QIKI ORION OS — Cold Boot`.
