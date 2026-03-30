# TASK-0004 — Ship BIOS truth absence

## Scope
- Target: `src/qiki/services/q_core_agent/core/ship_bios_handler.py` (unsafe areas around fallback and defaults).
- Goal: BIOS must not silently produce a green/OK report when real BIOS truth is unavailable.

## How It Was (unsafe)
- Protobuf `ImportError` path created mock BIOS classes unconditionally in module import path.
- Mock report defaulted to `all_systems_go=True` and `health_score=1.0`.
- Error paths from diagnostics could be interpreted as normal report flow (no explicit NoData contract).

## Why This Was Truth Substitution
- `ImportError` could silently switch source representation to mock classes.
- "No data" and "real nominal BIOS" were not explicitly separated at API level.
- Default green-like state (`all_systems_go=True`) could appear without confirmed report validity.

## What Changed
- Added explicit result contract:
  - `BiosFetchResult(ok, report, reason, is_fallback)`
  - `BiosReason`: `OK`, `BIOS_UNAVAILABLE`, `BIOS_TIMEOUT`, `BIOS_INVALID_REPORT`, `SIMULATED_BIOS`
- Added `process_bios_status_result()` for explicit truth/no-data semantics.
- Added report validation (`timestamp`, `post_results`, `all_systems_go`, device status presence/validity).
- Kept compatibility wrapper `process_bios_status()` but made it fail-fast:
  - returns report only on `ok`
  - raises on NoData/Invalid
- Added explicit fallback gate:
  - `QIKI_ALLOW_BIOS_FALLBACK=false` by default
  - fallback import path now fails fast unless explicitly enabled
  - fallback result is explicitly marked: `is_fallback=true`, `reason=SIMULATED_BIOS`, `all_systems_go=False`
- Updated `agent.py` BIOS handling to consume result contract when available and switch to safe mode on NoData.

## Canon Alignment
- No silent substitution of truth in production default path.
- BIOS absence/timeout/invalid report are now explicit facts.
- Fallback is opt-in and visibly marked, not confused with real BIOS truth.
