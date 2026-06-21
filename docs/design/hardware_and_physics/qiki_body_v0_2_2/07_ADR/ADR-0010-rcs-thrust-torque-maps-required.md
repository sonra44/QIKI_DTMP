# ADR-0010 — RCS requires Thrust Map and Torque Map

## Status

Accepted.

## Date

2026-06-20

## Context

RCS нельзя объявлять равномерной и полностью управляемой без расчёта.

QIKI имеет многогранное тело, RCS-кластеры, модули, байонеты, возможные внешние блоки и смещающийся центр масс.

## Decision

RCS requires Thrust Map and Torque Map before balanced thrust, all-axis control, safe docking burn, tumble recovery or full maneuverability can be claimed.

## Rejected alternatives

RCS is isotropic.

RCS has balanced thrust.

Full maneuverability without maps.

Manual thruster control as normal gameplay.

All-axis control verified without evidence.

## Consequences

RCS-related claims remain calculation-required until maps are provided.

Command gating must block or restrict unsafe burn modes when maps, CoM or inertia are unknown.

ORION must show map status and blockers.

## Related requirements

REQ-RCS-*; REQ-MASS-*; REQ-CMD-*; REQ-ORION-*.

## Related viewpoints

VP-06 Motion / RCS; VP-04 Mass / CoM / Inertia; VP-09 Command Safety.

## Related interfaces

IF-RCS-CMD-001; IF-CMD-BUS-001; IF-ORION-EVIDENCE-001.

## Related documents

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`; `05_ENGINEERING_RATIONALE.md`; `06_INTERFACE_CONTROL.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
