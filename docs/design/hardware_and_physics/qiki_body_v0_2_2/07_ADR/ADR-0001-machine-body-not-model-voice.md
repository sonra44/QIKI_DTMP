# ADR-0001 — QIKI is a machine body, not a model voice

## Status

Accepted.

## Date

2026-06-20

## Context

Главный риск QIKI — превратить её в голосовую оболочку языковой модели или персонажа в корпусе.

В таком случае модель может звучать убедительно, но физическая причинность тела будет исчезать. Модуль может быть “активен” в тексте, команда может быть “выполнена” голосом, а ORION может показать красивое состояние без runtime evidence.

## Decision

QIKI рассматривается как машинное тело.

Голос, модель и ORION не являются последней физической истиной. Последняя физическая истина должна идти из runtime state, simulation, telemetry, events, ACK, effect confirmation, audit and blackbox.

## Rejected alternatives

QIKI as AI assistant with a body shell.

QIKI as character whose claims are accepted as facts.

ORION as authoritative visual truth.

Model statement as physical confirmation.

## Consequences

Все физические утверждения должны иметь source.

Все действия должны иметь command lifecycle.

Все эффекты должны иметь effect confirmation.

ORION должен показывать evidence status.

Модель может объяснять и предполагать, но не подтверждать физический факт.

## Related requirements

REQ-BODY-001; REQ-BODY-002; REQ-BODY-003; REQ-AUDIT-*; REQ-ORION-*.

## Related viewpoints

VP-01 Runtime Truth; VP-02 Machine Body; VP-10 Operator Evidence.

## Related interfaces

IF-ORION-EVIDENCE-001; IF-AUDIT-001; IF-BLACKBOX-001.

## Related documents

`01_BODY_CANON.md`; `02_REQUIREMENTS.md`; `03_ARCHITECTURE_VIEWPOINTS.md`; `06_INTERFACE_CONTROL.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
