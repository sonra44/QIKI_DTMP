# TASK: EXEC_PLAN_P0 — ORION/QIKI_DTMP (sequential, evidence-based)

Date: 2026-02-02
Status: in_progress

## Canon / scope note (anti-drift)

- Priority canon (Now/Next) is **outside the repo**: `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`.
- This file is an **execution checklist** aligned to the current codebase (Feb 2026) so we can implement step-by-step without “magic”.
- Invariants:
  - Docker-first, Serena-first, evidence-only.
  - No mocks in UI.
  - No new `v2` / no duplicate subjects; extend current contracts with backward-compatible fields only.
  - One vertical slice at a time: implement → prove (tests/logs) → commit/push → memory checkpoint.

## North Star (Phase1 “playable”)

SoT → sim truth (`q_sim_service`) → telemetry/events → ORION → command → ACK → effect → incident lifecycle (ack/clear) → audit trail → replay proof.

## Map to “what exists now” (source-of-truth pointers)

### Power/EPS shedding (already implemented; needs spec + tests)
- `src/qiki/services/q_sim_service/core/world_model.py`
  - SoC hysteresis → shed: `radar`, `transponder` (reason `low_soc`)
  - Thermal trip flags → shed: `radar`, `transponder`, `nbl` (reason `thermal_overheat`)
  - NBL allow/budget gating (reason `nbl_budget` / `thermal_overheat`)
  - PDU overcurrent enforcement order: shed `nbl` → shed `radar` → shed `transponder` → throttle `motion` → throttle `rcs` → fault `PDU_OVERCURRENT`
- Existing tests (partial): `src/qiki/services/q_sim_service/tests/test_power_plane.py`

### Thermal plane (already implemented; needs warn policy + physical floor decision)
- `src/qiki/services/q_sim_service/core/world_model.py`:
  - Node config fields: `t_max_c` (`trip_c`) + `t_hysteresis_c` (`hys_c`)
  - Integration: explicit Euler, clamp temps to `[-120, 160]`
  - Trip state adds faults: `THERMAL_TRIP:<node>`
- Existing tests: `src/qiki/services/q_sim_service/tests/test_thermal_plane.py`

### Radar tracks (P0 trust baseline exists; needs COASTING + time split + LR/SR merge)
- Track store: `src/qiki/services/faststream_bridge/radar_track_store.py`
  - Alpha-beta filter; uses `max_misses`, `min_hits_to_confirm`
  - Today: `miss_count>0` ⇒ status `LOST` (needs COASTING)
  - Uses `frame.timestamp` (needs `ts_event` vs `ts_ingest` separation)
- Guard rules YAML exists: `src/qiki/resources/radar/guard_rules.yaml` (needs debounce/hysteresis + test matrix)

### Record/Replay (exists; extend proofs as needed)
- Core: `src/qiki/shared/record_replay.py` (`record_jsonl`, `replay_jsonl`, schema_version=1)
- CLI: `tools/nats_replay_jsonl.py`
- Integration proofs already exist under `tests/integration/` (record/replay incident repro, JSONL smoke).

## Milestones (global) + intermediate steps

### M0 — Preflight guardrails (every slice)

Steps:
1) Define 1-sentence goal + pass/fail criterion.
2) Confirm `origin/main == origin/master` after each slice.
3) Run minimal proof first, then full: `QUALITY_GATE_PROFILE=full bash scripts/quality_gate_docker.sh`.
4) Commit/push, then save `STATUS` + `TODO_NEXT` in Sovereign Memory + recall IDs.

### M1 — Load shedding: “spec + tests = no regressions”

Goal: make the current deterministic shedding order explicit and locked by tests (no guessing).

Intermediate steps:
1) Extract exact order and triggers from `q_sim_service/core/world_model.py` (SoC / thermal / PDU).
2) Write spec doc (canon) describing:
   - triggers (low_soc, thermal_overheat, pdu_overcurrent)
   - action order (shed loads, throttle loads, fault emission)
   - recovery behavior (hysteresis reset thresholds; re-enable when allowed)
3) Add/extend tests:
   - low SoC: `radar`, `transponder` in shed list; clears after `*_high_pct`.
   - thermal trip per node: expected shed loads and `THERMAL_TRIP:<node>` fault.
   - PDU overcurrent: ensure order is stable and throttles happen before fault.
4) Evidence: docker tests + ORION shows reasons (no N/A in related UI rows).

DoD:
- Spec exists and matches implementation.
- Tests cover each failure mode and pass in Docker.

### M2 — Thermal: warn policy + “no colder than ambient?” decision + tests

Goal: warn/trip/hysteresis becomes operator-proof and non-drifting.

Intermediate steps:
1) Decide warn rule:
   - derived warn = `trip_c - 10°C` (default), or explicit `t_warn_c` per node (optional).
2) Decide physical floor:
   - allow cooling below ambient (current code can) OR clamp `t >= ambient` (if desired).
3) Implement with backward compatibility:
   - add optional derived warn field in telemetry/UI (no schema break)
   - enforce non-zero hysteresis (warn if 0)
4) Tests:
   - warn threshold transitions
   - trip + clear with hysteresis
   - floor behavior (if clamped)

DoD:
- No alert “flap” at boundary; tests prove.
- ORION shows warn/trip clearly without mocks.

### M3 — Events/Incidents/ACK: unify without v2

Goal: stabilize operator workflow (commands/ACK/incidents) without introducing new protocol generations.

Intermediate steps:
1) Audit current `CommandMessage` + ACK envelope in existing subjects.
2) Add alias fields (e.g., `ok` alongside `success`, `request_id` alongside `requestId`) where missing.
3) Ensure ORION incident lifecycle publishes audit events (already done for incident_open) and remains deterministic for replay.
4) Add unit/integration tests proving backward compatibility.

DoD:
- Old consumers still work; new fields available.
- Replay proofs unaffected.

### M4 — Radar P0 trust: COASTING + time split + LR/SR merge + guard stabilization

Goal: tracks stable and guard rules non-flapping before any fancy render.

Intermediate steps:
1) Track lifecycle:
   - add COASTING when `miss_count > 0` but `<= max_misses`
   - degrade `quality` during coasting (deterministic formula)
2) Time:
   - add `ts_event` (sim time) and `ts_ingest` (processing time) fields to track/frame models (backward-compatible, optional)
3) LR/SR merge:
   - define deterministic merge rules to avoid duplicates
4) Guard rules:
   - add debounce/hysteresis config per rule (YAML)
   - incident key = `{rule_id}:{track_id}` (no duplicates)
5) Tests:
   - COASTING transitions
   - LR/SR merge cases
   - rule matrix (positive/negative/borderline)

DoD:
- Docker tests prove behavior on noisy/missing detections.

### M5 — Record/Replay: “same input → same state”

Goal: make regressions reproducible and provable.

Intermediate steps:
1) Confirm JSONL schema stays `schema_version=1` and includes needed timestamps.
2) Add replay modes (speed/no_timing already exist); add “step” if needed.
3) Add integration proof:
   - record known sequence
   - replay into isolated prefix
   - assert deterministic final state / incident lifecycle

DoD:
- Failing behavior becomes a replayable file + test.

### M6 — Renderer stack (P1; gated)

Gating condition: only start after M4 trust is green.

## Per-slice checklist (anti-scope creep)

For each slice:
- 1 goal + 1 DoD
- 1 new/extended test
- 1 evidence run in Docker
- 1 commit, push, sync `origin/main==origin/master`
- 1 memory checkpoint: `STATUS` + `TODO_NEXT` + recall IDs

