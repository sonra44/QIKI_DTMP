# TASK-0003 — Ship actuators truthful execution

## Scope
- Target: `src/qiki/services/q_core_agent/core/ship_actuators.py` (UNSAFE around protobuf import fallback and command success semantics).
- Goal: remove silent success / silent substitution in actuator execution path.

## How it was (unsafe)
- `ship_actuators.py` had `except ImportError` around protobuf imports and silently switched to local mock classes.
- Actuator methods (`set_main_drive_thrust`, `fire_rcs_thruster`, `activate_sensor`, `deactivate_sensor`) returned `True/False` only.
- `True` was used as "success" even when no execution proof existed (only best-effort send).
- In minimal/fallback contexts command path could be non-operational while higher layers still interpreted bool success as truth.

## Why this was truth substitution
- Fact "command accepted/executed/unavailable/timeout/rejected" was collapsed into plain bool.
- Missing ACK/confirmation was not explicitly represented.
- Import fallback could activate without explicit stand/dev intent.

## What changed (truthful model)
- Added explicit result contract:
  - `ActuationStatus`: `ACCEPTED | EXECUTED | REJECTED | FAILED | TIMEOUT | UNAVAILABLE`
  - `ActuationResult`: `status`, `reason`, `command_id`, `correlation_id`, `is_fallback`
- Added fail-fast default for protobuf import fallback:
  - `QIKI_ALLOW_ACTUATOR_FALLBACK=false` (default): import fallback raises, no silent mock substitution.
  - `true`: fallback allowed explicitly (stand/dev only).
- Added internal `_dispatch_command(...)` that maps outcomes deterministically:
  - `TimeoutError` -> `TIMEOUT`
  - `ConnectionError` -> `UNAVAILABLE`
  - `ValueError` -> `REJECTED`
  - other exceptions -> `FAILED`
  - successful send without execution ack -> `ACCEPTED` (not `EXECUTED`)
- In fallback/minimal mode:
  - allowed only with explicit flag, returns `is_fallback=true`, `reason=SIMULATED_ACTUATION`.
  - otherwise returns explicit `UNAVAILABLE`.
- Added result-first methods:
  - `set_main_drive_thrust_result(...)`
  - `fire_rcs_thruster_result(...)`
  - `activate_sensor_result(...)`
  - `deactivate_sensor_result(...)`
- Legacy bool methods are retained as compatibility wrappers (`True` only for `ACCEPTED/EXECUTED`).

## Canon check
- "Accepted" and "Executed" are no longer conflated: this layer currently reports `ACCEPTED` when only dispatch success is known.
- No silent synthetic success in default production profile.
- Stand fallback is explicit, visible in result (`is_fallback=true`) and logs.
