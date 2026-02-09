# TASK: Anti-loop guardrails for operator-visible progress

**ID:** TASK_20260209_ANTILOOP_GUARDRAILS  
**Status:** done  
**Owner:** codex  
**Date created:** 2026-02-09  

## Goal

Stop "evidence-only" loops by enforcing one operator-visible scenario per product cycle.

## Operator Scenario (visible outcome)

- Who: operator/developer validating ORION loop health.
- Outcome: every product cycle now must include explicit operator-facing delta and measurable impact, otherwise gate fails.
- Constraint: one cycle maps to one explicit scenario.

## Reproduction Command

```bash
bash scripts/ops/anti_loop_gate.sh
```

## Before / After

- Before: product changes could pass without explicit operator scenario + impact metric.
- After: quality gate runs anti-loop checks and fails when required sections are missing.

## Impact Metric

- Metric: required operator-visibility fields per product cycle.
- Baseline: `0` mandatory fields enforced by gate.
- Target: `4` mandatory fields enforced by gate.
- Actual: `4` fields enforced (`Operator Scenario`, `Reproduction Command`, `Before / After`, `Impact Metric`).

## Scope / Non-goals

- In scope:
  - Add anti-loop gate script.
  - Wire gate into quality gate.
  - Update task/PR templates and ops docs.
- Out of scope:
  - New product features.
  - Serena reindex.
  - Docker deep cleanup policy changes.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `scripts/ops/anti_loop_gate.sh`
  - `scripts/quality_gate_docker.sh`
  - `docs/ops/ANTI_LOOP_POLICY.md`
  - `TASKS/TEMPLATE_TASK.md`

## Plan (steps)

1) Add anti-loop gate script with hard checks for scenario + metric fields.
2) Integrate anti-loop script into quality gate.
3) Update templates and runbook documentation.

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (if behavior changed)
- [x] Операционный сценарий воспроизводится по команде из `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean (`git status --porcelain` is expected before merge)

## Evidence (commands → output)

- `bash scripts/ops/anti_loop_gate.sh` -> `OK` for this cycle dossier.
- `bash scripts/quality_gate_docker.sh` -> includes `Anti-loop gate` stage.

## Notes / Risks

- Strict gate can block legacy branches lacking updated task dossiers.
- Use temporary override only for emergency maintenance: `QUALITY_GATE_RUN_ANTI_LOOP=0`.

## Next

1) Apply the same task-dossier structure to next product slice.
2) Enforce PR template sections in CI when PR body file is available.
