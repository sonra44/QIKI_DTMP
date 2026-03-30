# TASK: BIOS HTTP shutdown is no longer silent

**ID:** TASK_20260127_BIOS_HTTP_SHUTDOWN_NO_SILENT  
**Status:** completed (verified 2026-02-09)  

## Goal

When stopping the BIOS HTTP server, do not swallow shutdown exceptions silently. Log at debug and continue cleanup.

## Implementation

- Safe shutdown helper: `src/qiki/services/q_bios_service/main.py`
  - `_safe_http_server_shutdown()` logs `bios_http_server_shutdown_failed` with `exc_info=True`.

## Evidence

- No silent swallow in module:
  - `rg -U -n "except Exception:\\s*\\n\\s*pass" src/qiki/services/q_bios_service/main.py`
- Unit test:
  - `pytest -q tests/unit/test_bios_http_shutdown_no_silent.py`
## Operator Scenario (visible outcome)
- Developer stops BIOS HTTP server; shutdown exceptions must be visible (debug log), not silently swallowed.

## Reproduction Command
```bash
pytest -q tests/unit/test_bios_http_shutdown_no_silent.py
```

## Before / After
- Before: Shutdown exception was swallowed (no evidence).
- After: Shutdown exception logs debug event `bios_http_server_shutdown_failed` and cleanup continues.

## Impact Metric
- Metric: silent-swallow blocks in BIOS HTTP shutdown path
- Baseline: 1 silent swallow
- Actual: 0 silent swallow; unit test asserts debug log record
