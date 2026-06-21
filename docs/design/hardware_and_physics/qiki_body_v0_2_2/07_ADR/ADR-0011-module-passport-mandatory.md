# ADR-0011 — Module passport is mandatory

## Status

Accepted.

## Date

2026-06-20

## Context

Название модуля ничего не доказывает.

Без паспорта “radiation shield”, “sensor boom”, “reactor block”, “NBL transmitter”, “field drive”, “extra tank” or “compute module” остаются словами, а не частью тела.

## Decision

Module passport is mandatory for runtime-ready module status.

A module without passport is not a runtime module.

## Rejected alternatives

Module installed only by name.

Module active without power / thermal / state.

Module gives capability without cost.

Module runtime-ready without passport.

Module implemented without evidence.

## Consequences

Каждый модуль должен иметь mount point, mass, CoM / inertia impact, power profile, thermal profile, capabilities, costs, blocked commands, failure modes, reason_codes, telemetry fields, audit and blackbox relevance.

ORION must show passport status.

## Related requirements

REQ-MODULE-*; REQ-GEOM-*; REQ-MASS-*; REQ-POWER-*; REQ-THERMAL-*.

## Related viewpoints

VP-08 Modularity / Module Passport; VP-03 Geometry / Mounting.

## Related interfaces

IF-MODULE-PASSPORT-001; IF-ORION-EVIDENCE-001; IF-AUDIT-001.

## Related documents

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`; `06_INTERFACE_CONTROL.md`; `09_ACCEPTANCE_CHECKS.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
