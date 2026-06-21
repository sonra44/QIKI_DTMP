# ADR-0008 — Field drive is not baseline

## Status

Accepted.

## Date

2026-06-20

## Context

Field drive может легко превратиться в baseline “тягу от чистой энергии”.

Это стирает рабочее тело, RCS-геометрию, Thrust Map, Torque Map, thermal model, mass / CoM / inertia and command safety.

## Decision

Field drive is not baseline.

If used, field drive must be Terta-exotic / advanced speculative / scenario-specific and must have explicit cost, limits, risk, cooldown, evidence path, audit and blackbox relevance.

## Rejected alternatives

Field drive baseline.

Pure energy thrust.

Reactionless normal drive.

Drive without cost.

Free acceleration.

## Consequences

Baseline motion remains RCS and physically constrained propulsion.

Field drive cannot bypass command gating, power, thermal, evidence or status marking.

Any use must be explicit and costly.

## Related requirements

REQ-FIELD-*; REQ-RCS-*; REQ-POWER-*; REQ-THERMAL-*; REQ-CMD-*.

## Related viewpoints

VP-06 Motion / RCS; VP-12 Engineering Rationale.

## Related interfaces

IF-RCS-CMD-001; IF-PDU-POWER-001; IF-THERMAL-TELEM-001; IF-CMD-BUS-001.

## Related documents

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`; `05_ENGINEERING_RATIONALE.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
