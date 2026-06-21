# ADR-0013 — Reader manual is derived; repo package is primary

## Status

Accepted.

## Date

2026-06-20

## Context

Reader manual нужен для удобного чтения, но он может стать параллельной правдой, если считать его главным source of truth.

## Decision

`10_READER_MANUAL.md` is a derived readable build.

Primary source files are `00_INDEX.md` through `09_ACCEPTANCE_CHECKS.md` and `07_ADR/`.

If reader manual conflicts with source files, source files win.

## Rejected alternatives

Reader manual as sole source of truth.

Manual prose overrides requirements.

Manual prose overrides ADR.

Manual prose becomes runtime claim.

## Consequences

Reader manual может быть удобной сборкой, но не заменяет BODY_CANON, REQUIREMENTS, CALCULATION_FRAME, INTERFACE_CONTROL or ADR.

Agents must not convert reader prose into implementation claims.

## Related requirements

REQ-REPO-*; REQ-ADR-*.

## Related viewpoints

VP-11 Repository Governance.

## Related interfaces

No runtime interface. Documentation governance only.

## Related documents

`00_INDEX.md`; `10_READER_MANUAL.md`; all primary source files.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
