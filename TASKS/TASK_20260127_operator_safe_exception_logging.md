# TASK: Operator-safe exception logging (ORION)

**ID:** TASK_20260127_OPERATOR_SAFE_EXCEPTION_LOGGING  
**Status:** completed (verified 2026-02-09)  

## Goal

ORION must not swallow exceptions silently inside the TUI runtime. Failures should be visible as debug logs (no TUI print jitter).

## Implementation

- All `except Exception: pass` blocks in ORION were upgraded to debug logging:
  - `src/qiki/services/operator_console/main_orion.py`

## Evidence

- No silent swallow in ORION:
  - `rg -U -n "except Exception:\\s*\\n\\s*pass" src/qiki/services/operator_console/main_orion.py`
- Sanity test that imports/parses ORION source:
  - `pytest -q tests/unit/test_telemetry_dictionary.py::test_orion_inspector_provenance_keys_are_covered_by_dictionary`
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
