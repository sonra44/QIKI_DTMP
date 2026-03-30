---
name: qiki-sensor-plane-auditor
description: Audit a QIKI_DTMP sensor path from config and world model through exported telemetry into ORION rendering. Use for missing sensor values, status mismatches, alias confusion, and truth-vs-mock questions.
---

# QIKI Sensor Plane Auditor

Trace one sensor or sensor group end-to-end without inventing a second truth source.

## Use when

- a sensor value is missing in ORION
- status or reason text looks wrong
- a new sensor is being added
- the question is whether a sensor is simulated, derived, projected, or mocked

## Do not use when

- the issue is general runtime ownership; use `qiki-runtime-contour-verifier`
- the issue is about broad provenance across many subsystems; use `qiki-provenance-map`

## Required invariants

- Bootstrap context first if needed.
- Treat simulator/config output as upstream truth unless code proves otherwise.
- `N/A` is only a dev or contract error, not a gameplay state.
- Do not patch UI wording before tracing config -> simulation -> export -> render.

## Evidence targets

- `src/qiki/services/q_core_agent/config/bot_config.json`
- `src/qiki/services/q_sim_service/core/world_model.py`
- `src/qiki/services/q_sim_service/service.py`
- `src/qiki/shared/models/telemetry.py`
- `src/qiki/services/operator_console/orion_v/hardware_view_model/collector.py`
- any local renderer or widget file for the affected field

## Procedure

1. Name the exact sensor or field under audit.
2. Prove whether it is configured.
3. Trace where simulation or derived state computes its value, status, and reason.
4. Verify telemetry/export fields and aliases.
5. Verify ORION collector and render path expectations.
6. Produce a compact matrix and mark the first broken link.

## Output

- `Sensor:` name
- `Configured:` yes/no
- `Simulated:` yes/no
- `Exported:` yes/no
- `Rendered:` yes/no
- `Mismatch:` exact link that breaks
- `Patch zone:` smallest file/module to change

## Rules

- Use exact field names and aliases from code.
- Separate raw truth, derived value, and UI projection.
- If the sensor is absent by design, say so explicitly instead of implying a bug.
