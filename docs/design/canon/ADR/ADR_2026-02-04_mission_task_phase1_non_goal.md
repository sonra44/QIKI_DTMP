# ADR: Mission/Task data is not a Phase1 goal (no producer; no-mocks)

**Status:** ACCEPTED  
**Date:** 2026-02-04  
**Decision owner:** ORION/QIKI_DTMP maintainers  

## Context

ORION contains a `Mission control/Управление миссией` screen and mission/task UI blocks.
However, Phase1 currently has **no simulation-truth producer** publishing mission/task state on `qiki.events.v1.>` (or any other canonical subject).

The project explicitly follows **no-mocks** policy: UI must not invent “demo” mission/task values or random progress.

The canon “real data matrix” already states that mission/task is **not implemented** in Phase1:

- `docs/operator_console/REAL_DATA_MATRIX.md`

Unit tests also assert the expected empty-state behavior:

- `tests/unit/test_orion_mission_seed_row_message.py`
- `tests/unit/test_orion_summary_mission_no_data_message.py`

## Decision

1) Mission/task data is **NOT a Phase1 goal** until a simulation-truth producer exists.
2) ORION must render mission/task as an explicit empty state: `No mission/task data/Нет данных миссии/задач`.
3) Any future mission/task implementation must publish under the existing canonical namespace `qiki.events.v1.>` (no v2/duplicates) and must be simulation-truth (no random/demo).

## Consequences

Positive:

- Eliminates drift and recurring “why is mission empty?” debates.
- Keeps ORION trustworthy under no-mocks: no fake mission/task numbers.
- Preserves a clean upgrade path when a real producer is added.

Negative / costs:

- The Mission screen remains informationally empty in Phase1.
- Any future mission/task work must first define a producer and contract, then update UI.

## Alternatives considered

1) **Add a placeholder/random mission producer**
   - Rejected: violates no-mocks (would create untrusted UI).
2) **Derive mission/task from unrelated telemetry**
   - Rejected: not simulation-truth; creates hidden coupling and likely drift.
3) **Hide/remove Mission UI**
   - Rejected: screen exists and is useful as a stable placeholder; it already has a correct empty-state.

