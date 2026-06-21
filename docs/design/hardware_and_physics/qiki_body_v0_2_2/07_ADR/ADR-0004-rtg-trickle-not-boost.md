# ADR-0004 — RTG is a trickle source, not boost-source

## Status

Accepted.

## Date

2026-06-20

## Context

RTG-class source легко размягчить до “маленькой вечной батарейки”.

Такое описание разрушает масштаб QIKI, отменяет supercap, thermal model, массу, сигнатуру и ограничения пиковых действий.

## Decision

RTG-class source является heavy / trickle source.

RTG-class source не является boost-source.

RTG может поддерживать survival, drift, cold-zone, sleep and slow recharge, но не должен напрямую питать пиковые действия.

## Rejected alternatives

RTG battery.

RTG boost.

RTG solves power.

Infinite energy.

Small RTG face module without speculative / Terta-exotic marking and explicit cost.

## Consequences

RTG получает цену: масса, постоянное тепло, сигнатура, ограничения, тепловой след.

RTG не отменяет battery, supercap, PDU and thermal model.

Для малой QIKI RTG допустим как внешний тяжёлый модуль, heavy mission module or clearly marked Terta-derived trickle source.

## Related requirements

REQ-POWER-*; REQ-THERMAL-*; REQ-MODULE-*.

## Related viewpoints

VP-05 Power / Thermal; VP-12 Engineering Rationale.

## Related interfaces

IF-PDU-POWER-001; IF-POWER-TELEM-001; IF-THERMAL-TELEM-001.

## Related documents

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`; `05_ENGINEERING_RATIONALE.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
