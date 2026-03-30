# TASK: Ship FSM context set is no longer silent

**ID:** TASK_20260127_SHIP_FSM_NO_SILENT_CONTEXT_SET  
**Status:** completed (verified 2026-02-09)  

## Goal

Ship FSM must not swallow failures when writing to `context_data`. It should log debug and keep progressing.

## Implementation

- Safe setter: `src/qiki/services/q_core_agent/core/ship_fsm_handler.py`
  - `_safe_set_context_data()` logs `ship_fsm_context_data_set_failed` with `exc_info=True`.

## Evidence

- No silent swallow in module:
  - `rg -U -n "except Exception:\\s*\\n\\s*pass" src/qiki/services/q_core_agent/core/ship_fsm_handler.py`
- Unit test:
  - `pytest -q tests/unit/test_ship_fsm_context_data_set_no_silent.py`
## Operator Scenario (visible outcome)
- Developer runs Ship FSM; failures to write context_data must be visible (debug), not silent.

## Reproduction Command
```bash
pytest -q tests/unit/test_ship_fsm_context_data_set_no_silent.py
```

## Before / After
- Before: context_data write failure was swallowed silently.
- After: context_data write failure logs `ship_fsm_context_data_set_failed` at debug.

## Impact Metric
- Metric: silent-swallow blocks when writing FSM context_data
- Baseline: 1 silent swallow
- Actual: 0 silent swallow; unit test asserts debug log record
