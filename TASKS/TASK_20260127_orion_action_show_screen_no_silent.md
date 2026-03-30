# TASK: ORION show_screen action is no longer silent on failures

**ID:** TASK_20260127_ORION_ACTION_SHOW_SCREEN_NO_SILENT  
**Status:** completed (verified 2026-02-09)  

## Goal

Switching ORION screens must not silently ignore exceptions (sidebar/keybar/screen containers).

## Implementation

- Silent `except Exception: pass` blocks in `action_show_screen()` are replaced with debug logs:
  - `src/qiki/services/operator_console/main_orion.py`

## Evidence

- `rg -U -n "except Exception:\\s*\\n\\s*pass" src/qiki/services/operator_console/main_orion.py`
## Operator Scenario (visible outcome)
- Operator uses ORION; UI exceptions must not be silently swallowed.

## Reproduction Command
```bash
rg -U -n "except Exception:\s*\n\s*pass" src/qiki/services/operator_console/main_orion.py
```

## Before / After
- Before: ORION had silent exception swallow blocks (`except Exception: pass`).
- After: Silent swallow blocks were replaced with debug logging (`orion_exception_swallowed`).

## Impact Metric
- Metric: silent-swallow patterns in ORION (main_orion.py)
- Baseline: >0
- Actual: 0 (pattern not present)
