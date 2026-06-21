# ADR-0009 — Bayonet requires mechanical hard lock

## Status

Accepted.

## Date

2026-06-20

## Context

Байонет может быть ошибочно описан как магнитный замок или простая стыковочная защёлка.

Но bayonet является mechanical, power, data and cascade interface; через него проходят внешние модули, питание, данные и нагрузки.

## Decision

Bayonet requires mechanical hard lock, structural check, electrical safety, umbilical mate, module handshake and passport validation before bridge allowed.

Magnetic pre-align is not structural lock.

Soft capture is not bridge allowed.

## Rejected alternatives

Magnetic lock as structural lock.

Soft capture allows power bridge.

Bridge active after contact.

Bayonet connected means module ready.

## Consequences

Bridge state requires explicit validation chain.

Aggressive burn may be blocked during soft capture / bridge active.

ORION must show bayonet state and blockers.

Audit must record state transitions.

## Related requirements

REQ-BAYONET-*; REQ-MODULE-*; REQ-CMD-*; REQ-ORION-*.

## Related viewpoints

VP-03 Geometry / Mounting; VP-08 Modularity / Module Passport; VP-09 Command Safety.

## Related interfaces

IF-BAYONET-MECH-001; IF-BAYONET-BRIDGE-001; IF-MODULE-PASSPORT-001.

## Related documents

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`; `05_ENGINEERING_RATIONALE.md`; `06_INTERFACE_CONTROL.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
