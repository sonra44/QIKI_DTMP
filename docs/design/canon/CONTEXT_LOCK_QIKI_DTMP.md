# QIKI_DTMP Context Lock (Canon)

Status: active
Date: 2026-03-01

## Purpose

Lock critical product and architecture decisions to prevent context drift and repeated regressions across sessions.

## Canonical locks

1. Product identity:
- QIKI_DTMP is a hardcore space sim-game with operator-console gameplay and AI-mediated interaction.

2. Primary UI/runtime:
- ORION V is the primary operator UI path.
- Legacy ORION is compatibility/reference only.

3. Radar rendering:
- Unicode renderer is mandatory baseline.
- Kitty/SIXEL are capability upgrades with automatic fallback.
- Mouse/click interaction is mandatory; keyboard fallback remains mandatory too.

4. Telemetry truth semantics:
- Runtime/UX states are explicit: `healthy`, `degraded`, `failed`, `off`.
- `N/A` is reserved for development or contract errors only.

5. Safety authority:
- `safe_mode` authoritative source is Q-Core Agent.
- Dual-source decision authorities are forbidden without an explicit ADR
  (sync 2026-07-10 with the operator lock `~/MEMORI/CONTEXT_LOCK_QIKI_DTMP.md`
  p.5, fixed there since 2026-03-01; the repo copy had drifted).

6. G1 mandatory telemetry additions (implementation lock):
- velocity vector + scalar;
- derived orbit metrics with confidence;
- split battery channels;
- comms link metrics;
- propellant pressure and oxidizer mass.
- Until these are implemented in runtime/schema, they are treated as mandatory backlog (not optional).

## Control loop (must pass before closing a cycle)

1. Documentation sync:
- update canon docs when behavior/contracts change.

2. Memory sync:
- save `STATUS`, `TODO_NEXT`, `DECISIONS`.

3. Proof:
- run recall and record returned IDs in task evidence.
