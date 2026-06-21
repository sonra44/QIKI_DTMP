# ADR-0005 — Reactor-class source is external / station / sled

## Status

Accepted.

## Date

2026-06-20

## Context

Reactor-class source нельзя делать обычным модулем на грань QIKI.

Иначе малое тело получает почти произвольную мощность без инфраструктурной, тепловой, механической и safety-цены.

## Decision

Reactor-class source является external / station / sled / heavy infrastructure.

QIKI может подключаться к нему только через validated structural-rated, electrically safe, thermally checked and passport-valid bridge.

## Rejected alternatives

Reactor module on face.

Reactor upgrade.

Normal reactor bayonet module.

Reactor directly powers all loads.

Reactor removes power limits.

## Consequences

Reactor-class source занимает внешний контур, требует bridge, PDU allowance, thermal clearance and motion restrictions.

Он не является face-mounted QIKI module.

Любое использование требует явного статуса и evidence path.

## Related requirements

REQ-POWER-*; REQ-BAYONET-*; REQ-MODULE-*; REQ-CMD-*.

## Related viewpoints

VP-05 Power / Thermal; VP-08 Modularity / Module Passport; VP-12 Engineering Rationale.

## Related interfaces

IF-BAYONET-BRIDGE-001; IF-MODULE-PASSPORT-001; IF-PDU-POWER-001.

## Related documents

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`; `05_ENGINEERING_RATIONALE.md`; `06_INTERFACE_CONTROL.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
