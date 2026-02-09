# TASK: Q-Sim no longer swallows exceptions silently

**ID:** TASK_20260127_Q_SIM_SERVICE_NO_SILENT_EXCEPTIONS  
**Status:** completed (verified 2026-02-09)  

## Goal

Remove silent `except Exception: pass` in Q-Sim service lifecycle and control loop glue; replace with debug logging.

## Implementation

- Control loop unsubscribe/close now logs debug on failures:
  - `src/qiki/services/q_sim_service/grpc_server.py`
- Invalid `RADAR_SR_THRESHOLD_M` now logs debug instead of silent pass:
  - `src/qiki/services/q_sim_service/service.py`

## Evidence

- No silent swallow in q_sim_service:
  - `rg -U -n "except Exception:\\s*\\n\\s*pass" src/qiki/services/q_sim_service`
## Operator Scenario (visible outcome)
- Q-Sim service handles shutdown/control glue; cleanup failures must be visible (debug), not silent.

## Reproduction Command
```bash
rg -U -n "except Exception:\s*\n\s*pass" src/qiki/services/q_sim_service
```

## Before / After
- Before: Some cleanup paths had silent swallow.
- After: Cleanup paths log debug on failure (unsubscribe/close; invalid env parsing logs debug).

## Impact Metric
- Metric: silent-swallow patterns in q_sim_service
- Baseline: >0
- Actual: 0 (pattern not present)
