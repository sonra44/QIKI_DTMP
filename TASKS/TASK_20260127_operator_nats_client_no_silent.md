# TASK: Operator console NATS client no longer swallows handler/ack errors

**ID:** TASK_20260127_OPERATOR_NATS_CLIENT_NO_SILENT  
**Status:** completed (verified 2026-02-09)  

## Goal

In the operator console NATS client, message handler failures and ack failures must not be swallowed silently.

## Implementation

- Message handler errors are logged at debug:
  - `src/qiki/services/operator_console/clients/nats_client.py`
  - Uses `_safe_ack()`; ack failures log `operator_nats_ack_failed ...`.

## Evidence

- No silent swallow in clients:
  - `rg -U -n "except Exception:\\s*\\n\\s*pass" src/qiki/services/operator_console/clients`
## Operator Scenario (visible outcome)
- Operator console receives NATS messages; handler/ack failures must be visible in logs (debug), not silent.

## Reproduction Command
```bash
rg -U -n "except Exception:\s*\n\s*pass" src/qiki/services/operator_console/clients/nats_client.py
```

## Before / After
- Before: Message handler/ack errors could be swallowed silently.
- After: Failures are logged at debug (handler failure + ack failure), while keeping best-effort ack.

## Impact Metric
- Metric: count of silent-swallow patterns in operator_console NATS client
- Baseline: >0
- Actual: 0 (pattern not present)
