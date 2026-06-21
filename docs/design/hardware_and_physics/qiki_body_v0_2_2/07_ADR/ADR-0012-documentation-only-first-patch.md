# ADR-0012 — First repository patch is documentation-only

## Status

Accepted.

## Date

2026-06-20

## Context

После сборки канона возникает риск сразу начать менять runtime-код, proto, NATS, gRPC, telemetry paths or ORION UI.

Это смешает три состояния: canon described, calculation frame defined, runtime implemented.

## Decision

The first repository patch for QIKI Body v0.2.2 must be documentation-only.

Runtime work requires a separate task and evidence.

## Rejected alternatives

Runtime implementation during first docs patch.

Proto / NATS / gRPC changes during documentation insertion.

Telemetry path changes during documentation insertion.

Tests implying runtime conformance without implementation.

Implemented by documentation.

## Consequences

Первый patch может создавать markdown files, ADR files, local index, acceptance checks and old GDD alignment note.

Он не должен менять runtime, generated files, ORION UI, MFD or telemetry.

No implemented claims without evidence.

## Related requirements

REQ-REPO-*; REQ-ADR-*.

## Related viewpoints

VP-11 Repository Governance.

## Related interfaces

No runtime interface. Repository governance only.

## Related documents

`00_INDEX.md`; `08_IMPLEMENTATION_BRIDGE.md`; `09_ACCEPTANCE_CHECKS.md`.

## Review notes

This ADR belongs to QIKI Body v0.2.2 Documentation Package.

This ADR is documentation-only.

It does not claim runtime implementation.

Implemented requires evidence.

Verified requires evidence and verification.
