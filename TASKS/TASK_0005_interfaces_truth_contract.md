# TASK-0005 — Interfaces truth contract (how it was / how it is now)

## Scope
- Target: `src/qiki/services/q_core_agent/core/interfaces.py:123`
- Adjacent consumer update: `src/qiki/services/q_core_agent/core/agent.py`

## How it was (unsafe)
- `QSimDataProvider.get_fsm_state()` around `:123` created synthetic `BOOTING/OFFLINE` snapshot by default.
- This default looked like a valid FSM fact, although provider did not own real FSM truth.
- Missing/externally-owned FSM data was silently adapted into a normal object.
- Consumer path (`AgentContext.update_from_provider`) accepted returned value as normal contract data.

## Why this was truth substitution
- Fact `FSM truth unavailable here` was replaced by `valid-looking snapshot`.
- Upstream logic could not distinguish:
  - `OK` (real truth),
  - `NO_DATA/UNAVAILABLE`,
  - `FALLBACK`.

## What changed
- Added explicit interface contract:
  - `InterfaceResult[T]` (`ok`, `value`, `reason`, `is_fallback`)
  - `InterfaceReason`: `OK`, `NO_DATA`, `UNAVAILABLE`, `INVALID`, `FALLBACK`
- `QSimDataProvider` and `GrpcDataProvider` now return `get_fsm_state_result()`:
  - default: `ok=False`, `value=None`, `reason=UNAVAILABLE` (or `NO_DATA` in StateStore mode)
  - fallback only when explicitly enabled with `QIKI_ALLOW_INTERFACE_FALLBACK=true`
  - fallback is always explicit: `ok=False`, `is_fallback=True`, `reason=FALLBACK`
- Legacy `get_fsm_state()` now fail-fast when truth is not available (`RuntimeError`), so no silent default object is returned.
- Consumer (`AgentContext.update_from_provider`) now reads `get_fsm_state_result()` and:
  - does not treat `ok=False` as normal,
  - raises on no-data,
  - allows explicit fallback only with warning and marker.

## Canon alignment
- Interface layer no longer turns absence of truth into valid-looking contract objects.
- `None` and fallback states are explicit and distinguishable from `OK`.
