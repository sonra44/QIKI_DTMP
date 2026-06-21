# ADR-0014 — ORION is evidence station, not decorative HUD

## Status

Accepted.

## Date

2026-06-20

## Context

ORION может стать красивой панелью, которая показывает желаемую картину вместо доказанного состояния.

Это создаёт интерфейсную ложь.

## Decision

ORION is an evidence station.

ORION must show source, freshness, trust, status, reason_codes, target-only, not implemented, calculation-required, ACK, effect confirmation, audit trail and blackbox relevance.

## Rejected alternatives

ORION as decorative HUD.

ORION green indicator as verified.

Panel active means module active.

UI confirms effect without effect confirmation.

ORION shows truth without source.

## Consequences

ORION должен различать source states and evidence quality.

If data is missing, stale, conflicting or target-only, ORION must show it.

ORION cannot invent physics.

## Related requirements

REQ-ORION-*; REQ-BODY-*; REQ-AUDIT-*.

## Related viewpoints

VP-10 Operator Evidence; VP-01 Runtime Truth.

## Related interfaces

IF-ORION-EVIDENCE-001; IF-AUDIT-001; IF-BLACKBOX-001.

## Related documents

`01_BODY_CANON.md`; `03_ARCHITECTURE_VIEWPOINTS.md`; `06_INTERFACE_CONTROL.md`; `09_ACCEPTANCE_CHECKS.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
