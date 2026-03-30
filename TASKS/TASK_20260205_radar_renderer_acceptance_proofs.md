# TASK: Radar renderer acceptance proofs (RFC baseline + enhanced)

**ID:** TASK_20260205_radar_renderer_acceptance_proofs  
**Status:** done  
**Owner:** codex  
**Date created:** 2026-02-05  

## Goal

Produce deterministic, Docker-first evidence that ORION radar renderer stack satisfies RFC acceptance without relying on terminal mouse/scroll quirks.

## Scope / Non-goals

- In scope:
  - Baseline acceptance proofs: wheel zoom + click selection + honest overlays/legend.
  - Enhanced acceptance proofs: `RADAR_RENDERER=auto` prefers bitmap backend when available, and falls back to Unicode on failure.
  - Operator-console runtime smoke that is independent of Termius/tmux mouse wheel.
- Out of scope:
  - “3D radar” rendering.
  - Web sidecar (Dash/Plotly).

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Radar visualization RFC: `docs/design/operator_console/RADAR_VISUALIZATION_RFC.md`
- Radar visualization ADR: `docs/design/canon/ADR/ADR_2026-02-04_radar_visualization_strategy.md`
- Key test file: `tests/unit/test_orion_radar_commands.py`
- Operator smoke skill: `.codex/skills/orion-operator-smoke/SKILL.md`

## Plan (steps)

1) Implement missing acceptance behaviors (legend honesty, pick radius scaling).
2) Add deterministic unit/run_test coverage for baseline mouse interactions.
3) Add deterministic unit/run_test coverage for enhanced auto-bitmap selection.
4) Add Docker-first operator-console smoke procedure as a repo skill.
5) Rebuild operator-console and prove health + invariants.

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands recorded below)
- [x] No-mocks preserved (missing data remains `N/A/—`)
- [x] Commits pushed to `main`
- [x] Operator-console smoke exists as a skill and is runnable

## Evidence (commands → output)

### Git evidence

Commits (pushed):
- `f915bdc` — legend shows selection, `LBL:req` honesty, zoom-scaled pick radius + tests.
- `7fdadc4` — new skill: `orion-operator-smoke`.
- `511050c` — tests: wheel zoom + click selection.
- `52b72af` — test: `RADAR_RENDERER=auto` selects bitmap backend when available.
- `69e2db8` — tests: Unicode IFF colors applied + `RADAR_RENDERER=auto` can select SIXEL backend.
- `8c19d2f` — test: honest empty state messaging for RUNNING/PAUSED/STOPPED (no mocked numbers).

### Unit evidence (Docker-first)

- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_radar_commands.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check tests/unit/test_orion_radar_commands.py`

### Runtime evidence (Docker-first, no mouse required)

- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build --force-recreate operator-console`
- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps operator-console`
- In-container headless smoke (see skill): `orion-operator-smoke` procedure asserts legend/LOD/pick behavior.

## Notes / Risks

- Termius + tmux mouse wheel passthrough is unreliable; evidence must not depend on it (see ADR).
- Mouse interactions are tested deterministically via Textual run_test and direct handler calls.

## Next

1) Keep running `orion-operator-smoke` as a standard proof step in future radar UX work.
