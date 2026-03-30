# ARTIFACT: Recovery Rebaseline Plan — 2026-03-05

Status: active
Date: 2026-03-05
Owner: codex + user

## Goal

Restore a truthful execution contour after scope drift: align claims, gates, and next actions with the actual blocker state before any new feature or polish work.

## Trigger

- Recent analysis showed that execution order drifted from the sequential plan in `TASKS/TASK_20260202_exec_plan_p0_sequential.md`.
- `M4` is still not green because the deterministic LR/SR merge continuity contract in `RadarTrackStore` is not fully restored.
- Later claims about renderer maturity, pilot readiness, and additional UI polish therefore need conditional wording until the gate is closed.

## Rebaseline Decision

1. Freeze new scope:
   - no new UI chrome/profile/status-bar refinement,
   - no new replay/session/plugin expansion,
   - no new radar capability work beyond blocker closure.
2. Restore gate order:
   - `M4` must be green before any further renderer/cutover advancement is claimed.
3. Reclassify workstreams:
   - `closed`: work with evidence and no dependency on unresolved `M4`,
   - `partial`: implemented, but downstream claims depend on unresolved trust/runtime blocker,
   - `backlog/drift`: valuable work outside the next critical path.

## Current Classification

### Closed

- `M1` deterministic load-shedding hardening.
- `M2` thermal warning persistence hardening.
- `M3` ACK/incident compatibility hardening.
- ORION semantic startup/Tier A readability slice.
- Anti-loop gate introduction itself.

### Partial / conditional

- `M4` radar trust hardening:
  - guard cadence slices are evidenced,
  - LR/SR merge continuity is still blocked,
  - therefore `M4` remains open.
- ORION V pilot/cutover claims:
  - stage docs and runbooks exist,
  - but readiness language must remain conditional until `M4` closes and stack status is re-proved from a clean state.

### Backlog / scope drift

- Additional ORION V chrome/profile polish after clickable acceptance.
- Further renderer/readability enhancements beyond the blocking trust contract.
- Session/runtime expansion not required for immediate gate closure.

## Mandatory Doc Corrections

1. `docs/CUTOVER_PLAN.md`
   - replace unconditional “executed/default” wording with conditional status.
2. `docs/ORION_V_RUNBOOK.md`
   - state that ORION V is the intended primary console, but operational readiness is conditional on unresolved blocker closure.
3. `TASKS/TASK_20260202_exec_plan_p0_sequential.md`
   - add explicit recovery update and freeze rule.
4. External canonical board `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
   - add a top-level recovery note and reopen `M4` as the active blocker.

## Next Single-Scope Cycle

Cycle name:
- `M4 LR/SR merge continuity closure`

Goal:
- restore deterministic `RadarTrackStore` continuity when only LR remains visible after SR observations.

Blocking proof:
- `src/qiki/services/faststream_bridge/tests/test_radar_track_store.py::test_track_store_keeps_sr_id_when_only_lr_is_visible`

DoD:
- targeted Docker pytest is green,
- related radar trust slice remains green,
- `M4` status can be updated from blocked to green with explicit evidence.

## Execution Update (2026-03-05)

Status:
- immediate blocker closed

Implemented:
- `src/qiki/services/faststream_bridge/radar_track_store.py`
  - added deterministic LR handoff fallback association for identity-bearing tracks when strict cartesian association fails after SR->LR range jump.

Docker evidence:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_track_store.py::test_track_store_keeps_sr_id_when_only_lr_is_visible`
  - `1 passed`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_track_store.py`
  - `5 passed`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_track_store.py src/qiki/services/faststream_bridge/tests/test_radar_guard_cadence.py`
  - `29 passed`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/faststream_bridge/radar_track_store.py src/qiki/services/faststream_bridge/tests/test_radar_track_store.py`
  - `All checks passed!`

Decision:
- The immediate `M4` blocker is no longer active.
- Recovery remains in effect, but the critical path can move from “close failing continuity test” to “reclassify M4 as green and choose the next controlled slice without reintroducing scope drift”.

## Stop Rules

- No new feature/polish work until the cycle above is either closed or explicitly re-scoped by the user.
- No new “pilot-ready/default” claims without fresh Docker evidence from the post-rebaseline state.
