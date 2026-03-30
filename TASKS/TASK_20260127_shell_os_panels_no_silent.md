# TASK: Shell OS panels do not swallow exceptions silently

**ID:** TASK_20260127_SHELL_OS_PANELS_NO_SILENT  
**Status:** completed (verified 2026-02-09)  

## Goal

Shell OS UI panels must not swallow exceptions silently in best-effort paths (e.g., data refresh / table clear).

## Implementation

- Debug logs replace silent passes in panel helpers:
  - `src/qiki/services/shell_os/ui/system_panel.py`
  - `src/qiki/services/shell_os/ui/services_panel.py`
  - `src/qiki/services/shell_os/ui/resources_panel.py`

## Evidence

- No silent swallow in shell_os:
  - `rg -U -n "except Exception:\\s*\\n\\s*pass" src/qiki/services/shell_os`
## Operator Scenario (visible outcome)
- Shell OS panels refresh; best-effort failures should be visible (debug logs), not silently ignored.

## Reproduction Command
```bash
rg -U -n "except Exception:\s*\n\s*pass" src/qiki/services/shell_os
```

## Before / After
- Before: Panel helper failures could be swallowed silently.
- After: Failures emit debug logs (e.g., table clear fallback / os-release read).

## Impact Metric
- Metric: silent-swallow patterns in shell_os
- Baseline: >0
- Actual: 0 (pattern not present)
