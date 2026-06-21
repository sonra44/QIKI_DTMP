# ADR-0006 — Baseline NBL is emergency low-rate only

## Status

Accepted.

## Date

2026-06-20

## Context

NBL легко превратить в магический канал связи через всё.

Если NBL сделать wideband, обычная связь, EMCON, задержки, потеря канала и драматургия изоляции теряют значение.

## Decision

Baseline NBL является emergency low-rate channel only.

NBL используется для коротких критических пакетов и требует criticality gating, SoC_cap, PDU allowance and thermal clearance.

## Rejected alternatives

NBL broadband.

NBL normal telemetry.

NBL data stream.

NBL video.

NBL internet through everything.

NBL bulk telemetry.

## Consequences

NBL не заменяет normal comms.

NBL требует reason_codes and audit.

Расширенный NBL возможен только как Terta-exotic с явной ценой и статусом.

## Related requirements

REQ-NBL-*; REQ-COMMS-*; REQ-POWER-*; REQ-THERMAL-*.

## Related viewpoints

VP-07 Sensor / Communication; VP-12 Engineering Rationale.

## Related interfaces

IF-NBL-001; IF-COMMS-001; IF-PDU-POWER-001; IF-AUDIT-001.

## Related documents

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`; `05_ENGINEERING_RATIONALE.md`; `06_INTERFACE_CONTROL.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
