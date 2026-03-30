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

## Execution update (2026-03-01) — M1 deterministic PDU shedding order

Goal:
- Lock PDU overcurrent non-critical shedding order in tests to avoid hidden behavioral drift.

Implemented:
- Added unit test:
  - `src/qiki/services/q_sim_service/tests/test_power_plane.py`
  - `test_pdu_overcurrent_sheds_noncritical_loads_in_deterministic_order`
- Scenario drives overcurrent with active `nbl + radar + transponder` and zero motion/RCS influence.
- Locked expected order: `nbl -> radar -> transponder`.
- Also asserts post-conditions: `nbl_allowed=false`, `nbl_power_w=0`, both channel allow flags false, no PDU throttle branch, bus current under limit.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/q_sim_service/tests/test_power_plane.py`
  - result: `................. [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-01) — M2 thermal config warning persistence

Goal:
- Lock thermal config warning behavior when `t_hysteresis_c <= 0` so warning does not disappear after runtime step.

Implemented:
- Added unit test:
  - `src/qiki/services/q_sim_service/tests/test_thermal_plane.py`
  - `test_thermal_config_warns_and_persists_when_hysteresis_is_zero`
- Test asserts:
  - warning is present at init: `THERMAL_PLANE_PARAM_INVALID:core:hys_zero`;
  - warning survives `step()` and remains in power faults telemetry.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/q_sim_service/tests/test_thermal_plane.py`
  - result: `....... [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-01) — M3 ACK alias/structure hardening

Goal:
- Strengthen deterministic coverage for control ACK aliases and structured rejection envelope.

Implemented:
- Added unit tests in `src/qiki/services/q_sim_service/tests/test_control_responses.py`:
  - `test_control_response_payload_falls_back_to_message_id_when_no_correlation_id`
  - `test_control_response_generic_rejection_has_structured_error_detail`
- Locked behavior:
  - `requestId`/`request_id` both use `metadata.message_id` when `correlation_id` is absent.
  - Generic rejection keeps `success=false` + `ok=false` and includes structured `error_detail` with `code/message/details.command_name`.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/q_sim_service/tests/test_control_responses.py`
  - result: `..... [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-05) — M3 grpc unblock + incident lifecycle audit coverage

Goal:
- Remove Phase1 blocker in `q-sim-service` startup and close missing lifecycle audit coverage in active ORION V path.

Implemented:
- Dependency lock for grpc compatibility in Docker dev image:
  - `requirements.txt`: pinned `grpcio==1.78.1` and `grpcio-tools==1.78.1` (exact pin required because 1.78.1 is yanked and range constraints may skip it).
- ORION V incident overlay clickability/runtime regression fix:
  - `src/qiki/services/operator_console/orion_v/widgets/alerts_overlay.py`
  - stale buttons now hide correctly after incident list shrink (`hidden_start = len(rendered_buttons)`).
- ORION V incident lifecycle test hardening:
  - `tests/unit/test_orion_v_app_incidents.py`
  - added explicit audit publish checks for:
    - `incident_open` on first-seen active incident,
    - `incident_ack` publish to `qiki.events.v1.operator.incidents`,
    - `incident_clear` publish to `qiki.events.v1.operator.incidents`,
    - overlay click selection + handler audit payload (`kind=incident_select`, `input_mode=mouse`),
    - regression: stale overlay buttons are hidden after list contraction.

## Recovery update (2026-03-05) — rebaseline after scope drift

Status:
- active

Observed problem:
- execution drifted beyond the intended gate order;
- `M4` is still not green because LR/SR merge continuity in `RadarTrackStore` remains blocked;
- downstream claims around renderer advancement and pilot/cutover readiness must therefore be treated as conditional.

Effective recovery rules:
1. Freeze new scope until the blocking `M4` continuity contract is closed.
2. Treat `M4` as the active critical path again.
3. Do not advance renderer/cutover status beyond “conditional” until `M4` is green with Docker proof.

Immediate next slice:
- `src/qiki/services/faststream_bridge/tests/test_radar_track_store.py::test_track_store_keeps_sr_id_when_only_lr_is_visible`

Reference:
- `TASKS/ARTIFACT_20260305_recovery_rebaseline_plan.md`

## Execution update (2026-03-05) — M4 LR/SR continuity blocker closed

Goal:
- restore deterministic SR->LR continuity and verify that the broader M4 trust slice remains green in Docker.

Implemented:
- `src/qiki/services/faststream_bridge/radar_track_store.py`
  - kept strict cartesian association as primary matcher;
  - added LR-only fallback handoff association for identity-bearing tracks using bearing/elevation continuity plus radial-velocity tolerance.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_track_store.py::test_track_store_keeps_sr_id_when_only_lr_is_visible`
  - result: `1 passed`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_track_store.py`
  - result: `5 passed`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_track_store.py src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `29 passed`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/faststream_bridge/radar_track_store.py src/qiki/services/faststream_bridge/tests/test_radar_track_store.py`
  - result: `All checks passed!`

Result:
- Immediate `M4` blocker is closed.
- Under the currently documented gate policy (`guard cadence stabilization` + `track-store merge continuity` in Docker), `M4` can now be treated as green.
- Drift sync for incident lifecycle audit subject in proof docs:
  - replaced legacy incident-proof references from `qiki.events.v1.operator.actions` to `qiki.events.v1.operator.incidents` in:
    - `TASKS/TASK_20260202_orion_incident_replay_proof.md`
    - `TASKS/TASK_20260202_thermal_trip_incident_proof.md`
    - `TASKS/TASK_20260202_radar_guard_incident_proof.md`
    - `TASKS/TASK_20260202_power_pdu_overcurrent_incident_proof.md`
    - `TASKS/TASK_20260202_thermal_incident_ack_clear_proof.md`
    - `docs/ORION_V_QUICKSTART.md`

Evidence (Docker, canonical path):
- `./scripts/run_integration_tests_docker.sh tests/integration/test_control_ack_envelope.py`
  - result: `1 passed`
- `./scripts/run_integration_tests_docker.sh tests/integration/test_record_replay_jsonl.py`
  - result: `1 passed`
- `./scripts/run_integration_tests_docker.sh tests/integration/test_record_replay_incident_repro.py`
  - result: `1 passed` (deterministic trigger path in test)
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_app_incidents.py`
  - result: all tests passed (`.......................`).

Notes:
- M3 ACK compatibility is green in unit+integration.
- Replay evidence is green with canonical per-file script runs; occasional compose restart races were observed in multi-file/batch attempts.

## Execution update (2026-03-01) — M4 radar guard cadence timing contract

Goal:
- Lock deterministic guard cadence timing behavior and close a runtime bug in min-duration handling.

Implemented:
- Bug fix in `src/qiki/services/faststream_bridge/radar_guard_cadence.py`:
  - moved `min_duration_s` extraction to rule-loop scope so it is always defined;
  - removed branch-local unbound usage that caused `UnboundLocalError`.
- Extended tests in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_time_source_is_canonical_timestamp_when_times_differ`
  - `test_guard_cadence_falls_back_to_timestamp_when_ts_event_missing`
- Time-source contract now explicit:
  - cadence uses `track.ts_event or track.timestamp`;
  - model-level normalization keeps canonical single time source (`timestamp`) when values diverge.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `.... [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `Ruff all passed`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-01) — M4 incident non-dup key stability

Goal:
- Lock deterministic incident dedup key shape and repeat-suppression behavior for repeated matches of the same rule/track pair.

Implemented:
- Updated key composition in `src/qiki/services/faststream_bridge/radar_guard_cadence.py`:
  - from `"{rule_id}|{track_id}"` to canonical `"{rule_id}:{track_id}"`.
- Added unit test in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_uses_stable_rule_track_dedup_key_and_suppresses_repeat`.
- Locked behavior:
  - cadence internal state contains key `"{rule_id}:{track_id}"` after first publish;
  - repeated matching update for the same active rule/track does not emit duplicate incident.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `..... [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `Ruff all passed`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-01) — M4 track-id churn + GC TTL invariants

Goal:
- Lock key lifecycle behavior for guard cadence under track-id churn and TTL garbage collection.

Implemented:
- Added unit tests in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_track_id_churn_creates_independent_keys`
  - `test_guard_cadence_gc_drops_only_stale_inactive_keys`
- Locked behavior:
  - Different `track_id` values under the same rule produce independent dedup keys/states.
  - Repeated matches for each active key remain edge-only (no duplicate publish).
  - GC removes stale inactive keys after TTL while preserving active keys.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `....... [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `Ruff all passed`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-01) — M4 key-scoped cooldown across tracks

Goal:
- Verify cooldown isolation per dedup key under simultaneous multi-track activity.

Implemented:
- Added unit test in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_cooldown_is_key_scoped_across_tracks`.
- Locked behavior:
  - publish for `track_b` is not suppressed by cooldown window of `track_a` (same rule, different key);
  - for `track_a`, re-entry before cooldown is suppressed and re-entry after cooldown publishes.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `........ [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `Ruff all passed`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-01) — M4 min-duration boundary (per-key)

Goal:
- Lock boundary semantics for per-key `min_duration_s` accumulation under short match gaps.

Implemented:
- Added unit test in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_min_duration_boundary_and_short_gaps_keep_window`.
- Locked behavior:
  - short gap `< min_duration_s` does not reset pending window;
  - publish happens exactly when elapsed time reaches boundary (`elapsed == min_duration_s`).

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `......... [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `Ruff all passed`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-01) — M4 min-duration reset on long gap (multi-track)

Goal:
- Verify per-key `min_duration` reset semantics when match gap is strictly greater than threshold under multi-track activity.

Implemented:
- Added unit test in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_min_duration_resets_on_gap_gt_threshold_per_key_with_multitrack`.
- Locked behavior:
  - for a given key, gap `> min_duration_s` resets pending window;
  - unrelated track activity does not alter timing state of this key;
  - publish occurs only after new post-reset accumulation reaches boundary.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `.......... [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `Ruff all passed`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-01) — M4 oscillation with hysteresis+cooldown

Goal:
- Lock edge/no-spam behavior when a key oscillates near threshold under combined hysteresis and cooldown.

Implemented:
- Added unit test in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_oscillation_with_hysteresis_and_cooldown_reentry`.
- Locked behavior:
  - oscillation inside hysteresis clear-band does not create duplicate publishes while key is active;
  - deactivation occurs only after leaving clear-band;
  - re-entry before cooldown is suppressed, re-entry after cooldown publishes.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `........... [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `Ruff all passed`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-01) — M4 default cooldown fallback contract

Goal:
- Validate and lock `default_cooldown_s` fallback semantics when rule-level `cooldown_s` is not explicitly set.

Implemented:
- Added unit test in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_uses_default_cooldown_when_rule_cooldown_missing`.
- Updated cadence logic in `src/qiki/services/faststream_bridge/radar_guard_cadence.py`:
  - treat `cooldown_s` as explicit only when it is present in `rule.model_fields_set`;
  - if not explicit, use `default_cooldown_s`;
  - explicit `cooldown_s` values (including `0`) keep precedence.
- Notes:
  - Initial test-first run failed and exposed prior behavior drift (`missing` was effectively treated as `0.0` due to `GuardRule` model defaults).
  - Runtime logic was corrected to match intended fallback contract.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `............ [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `Ruff all passed`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-01) — M4 explicit cooldown=0 precedence

Goal:
- Lock contract that explicit `cooldown_s=0` in rule must override `default_cooldown_s` fallback.

Implemented:
- Added unit test in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_explicit_zero_cooldown_overrides_default_fallback`.
- Locked behavior:
  - with rule explicit `cooldown_s=0`, re-entry is not suppressed by fallback default;
  - cadence publishes on immediate re-entry after deactivation.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `............. [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `Ruff all passed`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-01) — M4 malformed/non-finite cooldown fallback safety

Goal:
- Verify safety fallback behavior for malformed and non-finite `cooldown_s` values.

Implemented:
- Updated cadence logic in `src/qiki/services/faststream_bridge/radar_guard_cadence.py`:
  - if explicit cooldown is non-finite (`NaN`/`inf`) -> fallback to `default_cooldown_s`;
  - retains explicit finite numeric precedence (including `0`).
- Added tests in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_malformed_cooldown_uses_default_fallback`
  - `test_guard_cadence_nan_cooldown_uses_default_fallback`
- Note:
  - initial test-first run surfaced expected pydantic revalidation constraint when building `GuardTable` with malformed type; test adapted with lightweight table wrapper to validate runtime cadence fallback path directly.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `............... [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `Ruff all passed`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-01) — M4 +inf cooldown fallback safety

Goal:
- Verify `cooldown_s=+inf` safety path uses `default_cooldown_s` fallback and does not create permanent suppression.

Implemented:
- Added unit test in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_inf_cooldown_uses_default_fallback`.
- Locked behavior:
  - explicit `+inf` cooldown is treated as unsafe/non-finite and falls back to default cooldown;
  - suppression occurs during fallback window and publish resumes after it.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `................ [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `Ruff all passed`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-01) — M4 -inf/negative cooldown safety

Goal:
- Validate safety behavior for explicit `cooldown_s=-inf` and negative finite runtime values.

Implemented:
- Added unit tests in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_neg_inf_cooldown_uses_default_fallback`
  - `test_guard_cadence_negative_finite_cooldown_is_clamped_to_zero`
- Locked behavior:
  - explicit `-inf` is treated as non-finite/unsafe and falls back to `default_cooldown_s`;
  - negative finite cooldown is clamped to `0` (no suppression on re-entry).
- Note:
  - initial test-first run exposed GuardTable pydantic revalidation barrier for invalid cooldown values;
  - runtime-path tests use lightweight table wrapper to target cadence safety logic directly.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `.................. [100%]`
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `Ruff all passed`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-02) — M4 GC TTL stability under edge-case cooldown with many inactive keys

Goal:
- Lock GC TTL behavior when state contains many inactive keys and cooldown paths include explicit `0` and non-finite fallback values.

Implemented:
- Added unit test in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_gc_handles_many_inactive_keys_with_edge_cooldowns`
- Locked behavior:
  - for a large inactive key set (120 track IDs x 2 rules), GC removes stale inactive keys after TTL;
  - behavior is stable across edge cooldown paths:
    - explicit `cooldown_s=0`,
    - non-finite `cooldown_s=NaN` (runtime fallback to `default_cooldown_s`).

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `................... [100%]` (`19 passed`)
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `Ruff all passed`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-02) — M4 GC keeps recently reactivated keys under mixed cooldown

Goal:
- Verify GC TTL does not over-delete recently reactivated keys while still removing stale inactive keys under mixed cooldown paths.

Implemented:
- Added unit test in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_gc_keeps_recently_reactivated_keys_under_mixed_cooldowns`
- Locked behavior:
  - stale inactive keys are removed after TTL;
  - recently reactivated keys are preserved across GC trigger;
  - behavior is stable with mixed cooldown paths (`cooldown_s=0` and runtime non-finite fallback via `NaN`).

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `.................... [100%]` (`20 passed`)
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-02) — M4 min_duration reactivation window under long-gap churn

Goal:
- Verify that after a long inactive gap, a reactivated key starts a new `min_duration` accumulation window, and churn on other keys does not shortcut this window.

Implemented:
- Added unit test in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_min_duration_reactivation_after_long_gap_under_churn`
- Locked behavior:
  - initial activation still requires full `min_duration`;
  - after deactivation + long inactive gap, reactivation does not publish immediately;
  - publish occurs only at boundary (`elapsed >= min_duration`) for the reactivated key, independent of concurrent churn from other keys.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `..................... [100%]` (`21 passed`)
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-02) — M4 cooldown timestamp remains key-local after GC churn

Goal:
- Verify cooldown suppression timing remains key-local after GC churn for reactivated keys under mixed cooldown semantics.

Implemented:
- Added unit test in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_cooldown_timestamp_remains_key_local_after_gc_churn`
- Locked behavior:
  - GC removes stale inactive keys without disturbing recent key state;
  - after reactivation, explicit `cooldown_s=0` path emits immediately for the key;
  - non-finite cooldown fallback path for the same key remains suppressed until default cooldown expires.
- Test-first correction:
  - initial attempt failed due to wrong timing window (reactivation happened after fallback cooldown);
  - timeline corrected so early re-entry is inside fallback window, then outside it.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `...................... [100%]` (`22 passed`)
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-02) — M4 GC clear prevents old cooldown leak at min_duration boundary

Goal:
- Verify that after GC clears a stale inactive key, old cooldown timestamp from prior lifecycle does not leak into the new lifecycle at the reactivation `min_duration` boundary.

Implemented:
- Added unit test in `src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`:
  - `test_guard_cadence_gc_clear_prevents_old_cooldown_leak_at_min_duration_boundary`
- Locked behavior:
  - key state is removed by GC after TTL when inactive;
  - reactivation near former cooldown cutoff starts fresh `min_duration` accumulation;
  - publish at boundary is not suppressed by old lifecycle cooldown.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - result: `....................... [100%]` (`23 passed`)
- `bash scripts/quality_gate_docker.sh`
  - result: `exit 0`, `[anti-loop] OK`, `[quality-gate] OK`.

## Execution update (2026-03-02) — M1 ORION V shed reasons visibility closed

Goal:
- Close remaining M1 acceptance gap: ORION must show real shedding reasons (`power.shed_reasons`) with honest degraded marker when reasons are missing.

Implemented:
- Updated ORION V power module:
  - `src/qiki/services/operator_console/orion_v/modules/power.py`
  - Summary now includes `Причины сброса ...` sourced from `power.shed_reasons`.
  - Details now include explicit rows:
    - `Аварийное отключение нагрузки`
    - `Причины сброса`
  - If shedding is active and reasons are absent, details render `degraded: нет данных` (no mock defaults).
- Added i18n label:
  - `src/qiki/services/operator_console/orion_v/i18n_ru.py` (`shed_reasons`).
- Added unit coverage:
  - `tests/unit/test_orion_v_subsystem_modules.py`
  - `test_power_module_details_show_shed_reasons_from_telemetry`
  - `test_power_module_marks_missing_reasons_as_degraded_when_shedding_active`

Evidence:
- `docker compose -f docker-compose.phase1.yml run --rm qiki-dev bash -lc "pytest -q tests/unit/test_power_load_shedding_order.py src/qiki/services/q_sim_service/tests/test_power_plane.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_hardware_view_model.py tests/unit/test_orion_v_subsystem_modules.py"`
  - result: `.....................................................................    [100%]`
  - exit code: `0`

## Execution update (2026-03-02) — M1 true-final runtime-path closure (active ORION V)

Goal:
- Close M1 at active ORION V runtime path (`app -> hardware_view_model -> screens`) with explicit operator-visible shedding reasons and hard evidence.

Checklist:
- [x] `power.shed_reasons` wired into `HardwareCollector` power subsystem field set.
- [x] F2 (`systems`) renders dedicated `Причины сброса` line from hardware view model.
- [x] F1 (`cockpit`) renders `Аварийное отключение нагрузки` + `Причины сброса`.
- [x] Missing reasons under active shedding render `degraded: нет данных` (no fake defaults).
- [x] Runtime-path proof via `OrionVApp` `run_test` (F1/F2 visibility in active app path).
- [x] M1 missing test-cases covered: `nbl_budget`, `THERMAL_TRIP:core -> nbl`, positive `PDU_OVERCURRENT`.
- [x] Two independent auditors verdict: PASS/PASS.

Implemented:
- Active runtime wiring:
  - `src/qiki/services/operator_console/orion_v/hardware_view_model/collector.py`
  - `src/qiki/services/operator_console/orion_v/hardware_view_model/key_aliases.py`
  - `src/qiki/services/operator_console/orion_v/screens/systems.py`
  - `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
- Runtime-path and behavior tests:
  - `tests/unit/test_orion_v_app_incidents.py` (`test_telemetry_shed_reasons_visible_in_f1_and_f2_runtime_path`)
  - `tests/unit/test_orion_v_hardware_view_model.py`
  - `tests/unit/test_orion_v_systems_uses_hardware_model.py`
  - `tests/unit/test_orion_v_cockpit.py`
  - `tests/unit/test_power_load_shedding_order.py`
  - `src/qiki/services/q_sim_service/tests/test_power_plane.py`
  - Runtime test explicitly checks level visibility toggle `F2 -> F1` in active app path.

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/operator_console/orion_v/hardware_view_model/collector.py src/qiki/services/operator_console/orion_v/hardware_view_model/key_aliases.py src/qiki/services/operator_console/orion_v/screens/systems.py src/qiki/services/operator_console/orion_v/screens/cockpit.py tests/unit/test_orion_v_hardware_view_model.py tests/unit/test_orion_v_systems_uses_hardware_model.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py tests/unit/test_power_load_shedding_order.py src/qiki/services/q_sim_service/tests/test_power_plane.py`
  - result: `All checks passed!`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_hardware_view_model.py tests/unit/test_orion_v_systems_uses_hardware_model.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py tests/unit/test_power_load_shedding_order.py src/qiki/services/q_sim_service/tests/test_power_plane.py`
  - result: `........................................................................ [ 80%]` + `.................                                                        [100%]`
  - exit code: `0`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_power_load_shedding_order.py src/qiki/services/q_sim_service/tests/test_power_plane.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py tests/unit/test_orion_v_subsystem_modules.py tests/unit/test_orion_v_systems_uses_hardware_model.py`
  - result: `...............................................................          [100%]`
  - exit code: `0`
- Independent auditors:
  - `019cad95-404d-7ca1-b544-e73275d39327` -> `PASS`
  - `019cad95-547a-7620-909a-86f87ee4ac18` -> `PASS`

## Execution update (2026-03-02) — M2 true-final runtime-path closure (active ORION V)

Goal:
- Close remaining M2 acceptance gaps end-to-end: explicit thermal warn/trip policy evidence, floor decision evidence, and active ORION V runtime visibility in F2/F1.

Checklist:
- [x] Warn policy locked with tests: explicit `t_warn_c` override has priority over derived `trip - warn_delta`.
- [x] Trip/hysteresis boundary is stable (`trip` clear at `trip-hys`, no flap on boundary).
- [x] Ambient floor decision verified by tests:
  - overshoot below ambient from above is clamped to ambient;
  - below-ambient initial node is allowed and not clamped upward.
- [x] Active ORION V runtime path shows thermal warn/trip semantics in F2/F1 (`app -> hardware_view_model -> screens`).
- [x] F2 thermal key-contract drift fixed (`delta_t/heat_rate` stale keys removed; current thermal state keys used).
- [x] Canon docs sync for thermal proof criteria + real-data matrix thermal nodes fields.

Implemented:
- Thermal model evidence/tests:
  - `src/qiki/services/q_sim_service/tests/test_thermal_plane.py`
    - `test_thermal_warn_uses_explicit_t_warn_override`
    - `test_thermal_trip_boundary_is_stable_with_hysteresis`
    - `test_thermal_allows_node_to_remain_below_ambient_without_clamp_up`
- Active ORION V runtime-path wiring:
  - `src/qiki/services/operator_console/orion_v/hardware_view_model/collector.py`
    - thermal node extraction and operator fields: `core_state`, `warn_nodes`, `trip_nodes`, `core_warn_c`, `core_trip_c`, `core_hys_c`.
  - `src/qiki/services/operator_console/orion_v/hardware_view_model/key_aliases.py`
    - thermal subsystem keyset expanded with runtime thermal state keys.
  - `src/qiki/services/operator_console/orion_v/screens/systems.py`
    - F2 top thermal fields switched to runtime warn/trip keys.
  - `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
    - F1 thermal block renders `core` state, warn/trip node lists and thresholds from `thermal.nodes`.
- Runtime/behavior tests:
  - `tests/unit/test_orion_v_hwm_thermal.py`
  - `tests/unit/test_orion_v_systems_uses_hardware_model.py`
  - `tests/unit/test_orion_v_cockpit.py`
  - `tests/unit/test_orion_v_app_incidents.py` (`test_telemetry_thermal_warn_trip_visible_in_f1_and_f2_runtime_path`)
- Canon docs:
  - `docs/design/hardware_and_physics/thermal_plane_warn_and_floor.md`
  - `docs/operator_console/REAL_DATA_MATRIX.md`

Evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/operator_console/orion_v/hardware_view_model/collector.py src/qiki/services/operator_console/orion_v/hardware_view_model/key_aliases.py src/qiki/services/operator_console/orion_v/screens/systems.py src/qiki/services/operator_console/orion_v/screens/cockpit.py src/qiki/services/q_sim_service/tests/test_thermal_plane.py tests/unit/test_orion_v_hwm_thermal.py tests/unit/test_orion_v_systems_uses_hardware_model.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py`
  - result: `All checks passed!`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/q_sim_service/tests/test_thermal_plane.py tests/unit/test_orion_v_hwm_thermal.py tests/unit/test_orion_v_systems_uses_hardware_model.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py`
  - result: `.....................................................                    [100%]`
  - exit code: `0`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_hardware_view_model.py tests/unit/test_orion_v_hwm_diagnostics.py tests/unit/test_orion_v_hwm_thermal.py tests/unit/test_orion_v_systems_uses_hardware_model.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py src/qiki/services/q_sim_service/tests/test_thermal_plane.py`
  - result: `........................................................................ [ 79%]` + `...................                                                      [100%]`
  - exit code: `0`
