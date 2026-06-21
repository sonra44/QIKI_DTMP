# ADR-0007 — Protection is deployable deflector, not absolute shield

## Status

Accepted.

## Date

2026-06-20

## Context

Защиту легко описать как абсолютный щит.

Это уничтожает риск, геометрию, ориентацию, энергию, тепло, сенсорные конфликты, манёвренность and tactical choice.

## Decision

Protection is a constrained mechanism against a specific threat class, not an absolute shield.

Radiation deflector / deployable deflector can be used as a constrained protective mechanism with cost, geometry and degradation.

## Rejected alternatives

Absolute shield.

Full protection.

Invulnerable field.

Shield absorbs everything.

Protection without cost.

## Consequences

Защита должна иметь массу, энергию, тепло, геометрию, сенсорные конфликты, связь / EMCON effects, limitations, failure modes and reason_codes.

ORION должен показывать, от чего защита работает, какой ценой и с каким trust.

## Related requirements

REQ-PROTECT-*; REQ-POWER-*; REQ-THERMAL-*; REQ-SENSOR-*.

## Related viewpoints

VP-07 Sensor / Communication; VP-08 Modularity / Module Passport; VP-12 Engineering Rationale.

## Related interfaces

IF-MODULE-PASSPORT-001; IF-PDU-POWER-001; IF-THERMAL-TELEM-001; IF-ORION-EVIDENCE-001.

## Related documents

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`; `05_ENGINEERING_RATIONALE.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
