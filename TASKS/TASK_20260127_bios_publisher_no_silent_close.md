# TASK: BIOS NATS publisher close is no longer silent

**ID:** TASK_20260127_BIOS_PUBLISHER_NO_SILENT_CLOSE  
**Status:** completed (verified 2026-02-09)  

## Goal

When closing the BIOS NATS publisher, do not swallow drain/close exceptions silently. Log at debug and continue cleanup.

## Implementation

- Publisher close logging: `src/qiki/services/q_bios_service/nats_publisher.py`
  - Logs `bios_nats_publisher_drain_failed`
  - Logs `bios_nats_publisher_close_failed`

## Evidence

- No silent swallow in module:
  - `rg -U -n "except Exception:\\s*\\n\\s*pass" src/qiki/services/q_bios_service/nats_publisher.py`
- Unit test:
  - `pytest -q tests/unit/test_bios_nats_publisher_close_no_silent.py`
## Operator Scenario (visible outcome)
- Developer/service closes BIOS NATS publisher; drain/close failures must be visible (debug logs), not silent.

## Reproduction Command
```bash
pytest -q tests/unit/test_bios_nats_publisher_close_no_silent.py
```

## Before / After
- Before: Drain/close exceptions were swallowed silently.
- After: Drain/close exceptions log `bios_nats_publisher_drain_failed` / `bios_nats_publisher_close_failed` at debug.

## Impact Metric
- Metric: silent-swallow blocks in publisher close
- Baseline: 2 silent swallow
- Actual: 0 silent swallow; unit test asserts debug log records
