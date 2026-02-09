# TASK: Smoke tools are fail-loud (no silent exceptions)

**ID:** TASK_20260128_SMOKES_FAIL_LOUD_NO_SILENT  
**Status:** completed (verified 2026-02-09)  

## Goal

Smoke tools must not swallow exceptions silently in cleanup/unsubscribe paths; warnings must be visible to the operator.

## Implementation

- Replace silent passes with explicit warnings to stderr:
  - `tools/telemetry_smoke.py`
  - `tools/bios_status_smoke.py`
  - `tools/qiki_intent_smoke.py`
  - `tools/qiki_proposal_accept_smoke.py`
  - `tools/qiki_proposal_reject_smoke.py`

## Evidence

- No silent swallow in tools/scripts:
  - `rg -U -n "except Exception:\\s*\\n\\s*pass" tools scripts`
## Operator Scenario (visible outcome)
- Developer runs smoke tools; cleanup/unsubscribe errors must be visible (stderr warning), not silent.

## Reproduction Command
```bash
rg -U -n "except Exception:\s*\n\s*pass" tools scripts
```

## Before / After
- Before: Unsubscribe cleanup errors could be swallowed silently.
- After: Cleanup failures print WARN to stderr; no silent swallow patterns remain.

## Impact Metric
- Metric: silent-swallow patterns in tools/scripts
- Baseline: >0
- Actual: 0 (pattern not present)
