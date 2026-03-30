# TASK: Mission/Task is non-goal for Phase1 (canonize; prevent drift)

**Date:** 2026-02-04  
**Status:** done  

## Goal

Stop recurring drift around “mission/task should exist” in Phase1 by turning the current reality into an explicit, test-backed canon decision.

## Facts (source-of-truth)

- Canon real data matrix says mission/task has **no source** in Phase1:
  - `docs/operator_console/REAL_DATA_MATRIX.md` (row `Mission / Task`)
- Unit tests already assert empty-state behavior:
  - `tests/unit/test_orion_mission_seed_row_message.py`
  - `tests/unit/test_orion_summary_mission_no_data_message.py`

## Decision

- ADR: `docs/design/canon/ADR/ADR_2026-02-04_mission_task_phase1_non_goal.md`

Summary:
- Mission/task is **NOT a Phase1 goal** until a simulation-truth producer exists.
- ORION must keep rendering `No mission/task data/Нет данных миссии/задач`.
- Future mission/task must publish under `qiki.events.v1.>` (no v2/duplicates) and must be simulation-truth (no demo/random).

## Changes

- Updated the Real Data Matrix to explicitly label mission/task as Phase1 non-goal.
- Added ADR and linked it from `docs/design/canon/ADR/README.md`.
- Added a Phase1 note in `docs/design/operator_console/ORION_OS_SYSTEM.md` to prevent misreading freshness thresholds as “must exist now”.

## Evidence

### Repo search (no producer indicated by canon)

- `rg -n "Mission / Task" docs/operator_console/REAL_DATA_MATRIX.md`
- `rg -n "mission/task" docs/design/operator_console/ORION_OS_SYSTEM.md`

### Tests (Docker-first)

Run:
- `docker compose -f docker-compose.phase1.yml run --rm qiki-dev pytest -q tests/unit/test_orion_mission_seed_row_message.py tests/unit/test_orion_summary_mission_no_data_message.py`

Expected:
- tests pass

