# ADR-0015 — ACK is not effect confirmation

## Status

Accepted.

## Date

2026-06-20

## Context

ACK легко принять за успешное выполнение действия.

Для машинного тела это опасно: controller accepted не доказывает, что тело или мир изменились ожидаемым образом.

## Decision

ACK is not effect confirmation.

Command lifecycle must distinguish request, validation, allowed / rejected, publish, ACK, effect confirmation and audit.

## Rejected alternatives

ACK means complete.

Command accepted means effect happened.

Published means executed.

Allowed means done.

UI state replaces effect confirmation.

## Consequences

ORION должен отличать ACK от effect confirmation.

Audit должен хранить цепочку.

Critical actions require effect confirmation or explicit failure / timeout / partial status.

Postmortem analysis becomes possible.

## Related requirements

REQ-CMD-*; REQ-AUDIT-*; REQ-ORION-*.

## Related viewpoints

VP-09 Command Safety; VP-10 Operator Evidence; VP-01 Runtime Truth.

## Related interfaces

IF-CMD-BUS-001; IF-AUDIT-001; IF-ORION-EVIDENCE-001.

## Related documents

`01_BODY_CANON.md`; `02_REQUIREMENTS.md`; `06_INTERFACE_CONTROL.md`; `09_ACCEPTANCE_CHECKS.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
