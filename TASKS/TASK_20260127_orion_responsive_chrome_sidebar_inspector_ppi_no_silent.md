# TASK: ORION responsive chrome sidebar/inspector/PPI is non-silent on failures

**ID:** TASK_20260127_ORION_RESPONSIVE_CHROME_SIDEBAR_INSPECTOR_PPI_NO_SILENT  
**Status:** completed (verified 2026-02-09)  

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
