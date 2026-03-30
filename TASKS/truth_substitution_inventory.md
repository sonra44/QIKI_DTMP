# TASK-0001 Truth Substitution Inventory

Date: 2026-02-10
Scope: `src/` runtime paths (test-only files excluded)
Method: static scan (`rg`) + line-level verification

## Legend
- `DEV_ONLY`: acceptable only in explicit dev/mock execution path
- `PROD_FORBIDDEN`: must not execute in production
- `UNSAFE`: can silently substitute truth and needs redesign/fail-fast

| ID | File | Line | Type | What is substituted | Activates without explicit mock flag | Classification |
|---|---|---:|---|---|---|---|
| TS-001 | `src/qiki/services/q_core_agent/core/ship_bios_handler.py` | 51 | fallback | On proto import failure, assigns `Mock*` classes to `BiosStatusReport/DeviceStatus/UUID/Timestamp` | Yes (`except ImportError`) | `PROD_FORBIDDEN`, `UNSAFE` |
| TS-002 | `src/qiki/services/q_core_agent/core/ship_bios_handler.py` | 73 | default | `MockBiosStatusReport.all_systems_go = True` by default | Yes (when TS-001 path is hit) | `PROD_FORBIDDEN`, `UNSAFE` |
| TS-003 | `src/qiki/services/q_core_agent/core/ship_actuators.py` | 46 | fallback | On proto import failure, assigns `Mock*` actuator classes | Yes (`except ImportError`) | `PROD_FORBIDDEN`, `UNSAFE` |
| TS-004 | `src/qiki/services/q_core_agent/core/ship_bios_handler.py` | 31 | fallback | Relative-import fallback to local modules on `ImportError` | Yes (`except ImportError`) | `DEV_ONLY` |
| TS-005 | `src/qiki/services/q_core_agent/core/ship_actuators.py` | 35 | fallback | Relative-import fallback to local modules on `ImportError` | Yes (`except ImportError`) | `DEV_ONLY` |
| TS-006 | `src/qiki/services/q_core_agent/core/ship_fsm_handler.py` | 30 | fallback | Relative-import fallback to local modules on `ImportError` | Yes (`except ImportError`) | `DEV_ONLY` |
| TS-007 | `src/qiki/services/q_core_agent/main.py` | 155 | mock | `--mock` switches to `_MOCK_DATA_PROVIDER` | No (explicit CLI flag) | `DEV_ONLY` |
| TS-008 | `src/qiki/services/q_core_agent/core/neural_engine.py` | 92 | mock | Generates mock proposal when `mock_neural_proposals_enabled=true` | No (explicit config switch) | `DEV_ONLY` |
| TS-009 | `src/qiki/services/q_core_agent/core/grpc_data_provider.py` | 86 | default | On gRPC read error, returns synthetic `SensorData(... scalar_data=0.0)` | Yes (runtime RPC failure) | `PROD_FORBIDDEN`, `UNSAFE` |
| TS-010 | `src/qiki/services/q_core_agent/core/interfaces.py` | 123 | default | `QSimDataProvider.get_fsm_state()` synthesizes BOOTING state/context even without real FSM source | Yes (default branch when not using StateStore) | `PROD_FORBIDDEN`, `UNSAFE` |
| TS-011 | `src/qiki/services/faststream_bridge/app.py` | 418 | fallback | On frame handling exception, publishes fallback track built from empty detections | Yes (runtime exception path) | `PROD_FORBIDDEN`, `UNSAFE` |
| TS-012 | `src/qiki/services/q_core_agent/core/bios_http_client.py` | 15 | fallback | Returns explicit `bios_version="unavailable"` status when BIOS cannot be fetched | Yes (runtime fetch failure) | `DEV_ONLY` (explicitly marked unavailable; not fake green) |
| TS-013 | `src/qiki/services/faststream_bridge/metrics.py` | 7 | fallback | No-op Prometheus metrics when dependency missing | Yes (missing optional package) | `DEV_ONLY` |
| TS-014 | `src/qiki/services/q_core_agent/core/metrics.py` | 9 | fallback | No-op Prometheus metrics when dependency missing | Yes (missing optional package) | `DEV_ONLY` |

## Summary
- Total inventory items: 14
- `UNSAFE`: 6 (`TS-001`, `TS-002`, `TS-003`, `TS-009`, `TS-010`, `TS-011`)
- `PROD_FORBIDDEN`: 6
- `DEV_ONLY`: 8

## Notes
- `mission_control_tui.py` import guard is fail-fast (`sys.exit(1)`), so it is not a silent truth substitution path.
- This inventory is intentionally strict about runtime truth sources; test mocks were excluded.
