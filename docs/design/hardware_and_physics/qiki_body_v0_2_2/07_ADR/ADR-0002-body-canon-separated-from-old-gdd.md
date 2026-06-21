# ADR-0002 — Body canon is separated from old game GDD

## Status

Accepted.

## Date

2026-06-20

## Context

Старый GDD содержит исходные игровые идеи, корпус, модули, режимы, энергетические и лорные формулировки.

В нём могут оставаться мягкие или устаревшие утверждения: RTG как обычный источник, NBL как широкий канал, магнитный байонетный замок, абсолютная защита, реактор как модуль, field drive как чистая энергия.

## Decision

Актуальный канон тела QIKI выносится в отдельный hardware / physics documentation package.

Старый GDD сохраняется как game-design / historical layer и получает superseded / alignment note.

## Rejected alternatives

Удалить старый GDD.

Полностью переписать старый GDD первым патчем.

Оставить старый GDD без статуса.

Считать старый GDD равным BODY_CANON по аппаратной физике.

## Consequences

Старый GDD сохраняет исторический и игровой контекст.

BODY_CANON становится главным источником аппаратной логики тела.

Опасные старые формулировки помечаются superseded by v0.2.2.

Первый patch остаётся documentation-only.

## Related requirements

REQ-REPO-*; REQ-ADR-*.

## Related viewpoints

VP-11 Repository Governance; VP-12 Engineering Rationale.

## Related interfaces

No runtime interface. This is repository governance.

## Related documents

`00_INDEX.md`; `01_BODY_CANON.md`; `08_IMPLEMENTATION_BRIDGE.md`; `09_ACCEPTANCE_CHECKS.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
